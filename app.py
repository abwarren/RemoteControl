"""
PLO Remote Table Control - Flask Backend v3
Stability fixes over v2:
  P1 - _tables persisted to disk every 10s, reloaded on startup
  P2 - Stale seats evicted after SEAT_TTL seconds (background thread)
  P2 - Commands expire after CMD_TTL seconds (same thread)
  P2 - Disk writes moved outside _store_lock scope
  P3 - All print() replaced with app.logger (goes to journald)
  P3 - Rate limiting via flask-limiter (1 snapshot/sec per token)
  P3 - systemd restart protection in service file (see bottom comment)
"""

import os
import sys
import time
import hmac
import hashlib
import threading
import uuid
import logging
from datetime import datetime
from pathlib import Path
import json
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ── App setup ──────────────────────────────────────────────────────────────────

app = Flask(__name__)
# CORS(app)  # Disabled - nginx handles CORS

# Send Flask logs to stdout so systemd/journald captures them
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout,
)
app.logger.setLevel(logging.INFO)

# Rate limiter — 1 snapshot per second per IP
# Install: pip install flask-limiter --break-system-packages
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],          # no global limit; apply per route
    storage_uri="memory://",
)


# ── Auth & Session Management ──────────────────────────────────────────────────

from flask_login import LoginManager, login_required, current_user
from functools import wraps
from auth_models import User, init_database, log_user_activity, get_db_connection
import audit_logs
from werkzeug.security import generate_password_hash, check_password_hash

# Secret key for sessions
import secrets
secret_key_file = '/opt/plo-equity/.secret_key'
if not os.path.exists(secret_key_file):
    secret_key = secrets.token_hex(32)
    with open(secret_key_file, 'w') as f:
        f.write(secret_key)
    app.logger.info('[AUTH] Generated new secret key')
else:
    with open(secret_key_file, 'r') as f:
        secret_key = f.read().strip()

app.secret_key = secret_key
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'
login_manager.login_message = None  # Suppress flash messages

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# Helper decorator for admin-only routes
def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin():
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Initialize database
try:
    init_database()
    app.logger.info('[AUTH] Database initialized')
except Exception as e:
    app.logger.error(f'[AUTH] Database init failed: {e}')



# ── Environment ────────────────────────────────────────────────────────────────

N4P_SEAT_SECRET = os.getenv('N4P_SEAT_SECRET', 'default_secret_change_me')
TRACKER_API_KEY = os.getenv('TRACKER_API_KEY', 'trk_default')

# Tuning constants
SEAT_TTL    = int(os.getenv('N4P_SEAT_TTL',    '30'))   # seconds before stale seat evicted
CMD_TTL     = int(os.getenv('N4P_CMD_TTL',     '30'))   # seconds before unacked command expires
PERSIST_INT = int(os.getenv('N4P_PERSIST_INT', '10'))   # seconds between state snapshots to disk
STATE_FILE  = Path(os.getenv('N4P_STATE_FILE', '/opt/plo-equity/state_snapshot.json'))

# ── In-memory stores ───────────────────────────────────────────────────────────

_tables        = {}   # key: table_id → canonical table state
_command_queue = {}   # key: seat_token → command dict or None
_cashout_state = {}   # key: seat_token → {requested, available}
_bot_seats     = {}   # key: bot_id → {"table_id": str, "seat_index": int, "last_seen": float}
_seat_bots     = {}   # key: (table_id, seat_index) → bot_id
_store_lock    = threading.Lock()

# ── Hand history (multi-hand ASCII log, FIFO last 20) ──────────────────────────
_hand_history  = []   # list of ASCII hand strings, newest last, max 20
_hand_lock     = threading.Lock()
HAND_HISTORY_MAX = 20

# ── Static file serving ────────────────────────────────────────────────────────

@app.route("/")
def index():
    # Serve different UIs based on domain
    host = request.headers.get('Host', '')
    if 'rc2.' in host:
        return send_from_directory("static", "index.html")
    return send_from_directory("static", "remote.html")



@app.route("/shell")
def shell():
    """Frontend shell for monitoring all services"""
    return send_from_directory("static", "shell-live.html")
@app.route("/n4p.js")
def n4p_script():
    resp = send_from_directory("static", "n4p.js")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

# ── Helpers ────────────────────────────────────────────────────────────────────

def _archive_hand(table):
    """Archive the current hand as ASCII text and append to _hand_history.
    Called when hand_key changes (new deal detected).
    Format: hole cards line, flop line, turn line, river line, separator.
    No labels, no words, only cards. One line per street."""
    seats = table.get("seats", {})
    board = table.get("board", {})
    flop  = board.get("flop") or []
    turn  = board.get("turn")
    river = board.get("river")

    # Find hero seat hole cards (or any seat with hole cards)
    hole_cards = []
    for seat in seats.values():
        hc = seat.get("hole_cards") or []
        if hc:
            hole_cards = hc
            break

    if not hole_cards:
        return  # Nothing to archive

    lines = []
    lines.append(" ".join(hole_cards))
    if flop:
        lines.append(" ".join(flop))
    if turn:
        lines.append(turn)
    if river:
        lines.append(river)
    lines.append("------------------------")

    hand_text = "\n".join(lines)

    with _hand_lock:
        _hand_history.append(hand_text)
        if len(_hand_history) > HAND_HISTORY_MAX:
            _hand_history[:] = _hand_history[-HAND_HISTORY_MAX:]


def normalize_name(name):
    if not name:
        return None
    return str(name).strip().lower()


def make_hand_key(payload):
    return f"{payload.get('table_id')}:{payload.get('dealer_seat')}:{payload.get('deal_id')}"


def generate_seat_token(table_id, seat_no):
    msg = f"{table_id}:{seat_no}".encode('utf-8')
    return hmac.new(N4P_SEAT_SECRET.encode('utf-8'), msg, hashlib.sha256).hexdigest()


def get_or_create_table(table_id):
    if table_id not in _tables:
        _tables[table_id] = {
            "table_id":      table_id,
            "hand_key":      None,
            "state_version": 0,
            "last_ts":       0,
            "seats":         {},
            "seat_map":      {},
            "next_seat_no":  1,
            "variant":       "plo",
            "street":        None,
            "pot_zar":       0,
            "board":         {"flop": [], "turn": None, "river": None},
            "dealer_seat":   None,
        }
    return _tables[table_id]


def update_bot_seat_mapping(bot_id, table_id, seat_index):
    """
    Update bidirectional bot-seat mapping.
    Called when bot sends snapshot with is_hero seat.
    """
    if not bot_id or bot_id == 'unknown-bot':
        return  # Don't track unknown bots

    ts = time.time()

    # Update bot → seat mapping
    _bot_seats[bot_id] = {
        "table_id": table_id,
        "seat_index": seat_index,
        "last_seen": ts
    }

    # Update seat → bot mapping
    seat_key = (table_id, seat_index)
    _seat_bots[seat_key] = bot_id

    app.logger.info(f'[BOT_SYNC] {bot_id} → {table_id}:{seat_index}')


def clear_bot_seat(bot_id):
    """Remove bot from seat mapping (called when bot unseats)"""
    if bot_id not in _bot_seats:
        return

    info = _bot_seats[bot_id]
    seat_key = (info["table_id"], info["seat_index"])

    # Clear bidirectional mapping
    if seat_key in _seat_bots and _seat_bots[seat_key] == bot_id:
        del _seat_bots[seat_key]

    del _bot_seats[bot_id]
    app.logger.info(f'[BOT_SYNC] {bot_id} unseated')


def _build_seats_list(table):
    out = []
    # Always build exactly 9 seats for 9-max tables
    max_seats = 9
    for seat_no in range(1, max_seats + 1):
        seat = table["seats"].get(seat_no)
        token = generate_seat_token(table["table_id"], seat_no)
        cmd = _command_queue.get(token)
        pending_cmd = cmd["type"] if cmd and cmd.get("status") == "pending" else None

        # Look up bot identity for this seat
        seat_key = (table["table_id"], seat_no)
        bot_id = _seat_bots.get(seat_key)

        if seat:
            out.append({
                **seat,
                "pending_cmd": pending_cmd,
                "bot_id": bot_id,
            })
        else:
            # Empty seat placeholder
            out.append({
                "seat_no":    seat_no,
                "name":       None,
                "stack_zar":  0,
                "hole_cards": [],
                "status":     "empty",
                "is_dealer":  False,
                "is_hero":    False,
                "last_seen":  None,
                "pending_cmd": None,
                "bot_id":     None,
            })
    return out


def _table_view(table):
    return {
        "table_id":      table["table_id"],
        "variant":       table["variant"],
        "street":        table["street"],
        "pot_zar":       table["pot_zar"],
        "dealer_seat":   table["dealer_seat"],
        "board":         table["board"],
        "state_version": table["state_version"],
        "last_updated":  table["last_ts"],
        "seats":         _build_seats_list(table),
    }

# ── P1: State persistence ──────────────────────────────────────────────────────

def _serialise_state():
    """Return a JSON-safe snapshot of _tables (seats only — no lock held here)."""
    return {
        tid: {
            **{k: v for k, v in t.items() if k != "seats"},
            "seats": {
                str(sno): seat
                for sno, seat in t["seats"].items()
            }
        }
        for tid, t in _tables.items()
    }


def _load_state():
    """Load persisted state from disk into _tables on startup."""
    if not STATE_FILE.exists():
        return
    try:
        raw = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        for tid, t in raw.items():
            t["seats"] = {int(k): v for k, v in t.get("seats", {}).items()}
            _tables[tid] = t
        app.logger.info(f"[PERSIST] Loaded {len(_tables)} table(s) from {STATE_FILE}")
    except Exception as e:
        app.logger.warning(f"[PERSIST] Could not load state: {e}")


def _persist_loop():
    """Background thread: snapshot state to disk every PERSIST_INT seconds."""
    while True:
        time.sleep(PERSIST_INT)
        try:
            with _store_lock:
                snapshot = _serialise_state()
            # Disk write outside lock
            tmp = STATE_FILE.with_suffix('.tmp')
            tmp.write_text(json.dumps(snapshot, default=str), encoding='utf-8')
            tmp.replace(STATE_FILE)
        except Exception as e:
            app.logger.warning(f"[PERSIST] Write failed: {e}")

# ── P2: Stale seat eviction + command expiry ───────────────────────────────────

def _cleanup_loop():
    """Background thread: evict stale seats and expire old commands."""
    while True:
        time.sleep(10)
        now = time.time()
        try:
            with _store_lock:
                for table in list(_tables.values()):
                    # Evict seats not seen recently
                    live = {
                        sno: seat for sno, seat in table["seats"].items()
                        if seat.get("last_seen") and (now - seat["last_seen"]) < SEAT_TTL
                    }
                    evicted = len(table["seats"]) - len(live)
                    if evicted:
                        table["seats"] = live
                        app.logger.info(
                            f"[CLEANUP] table={table['table_id']} evicted {evicted} stale seat(s)"
                        )

                # Expire old commands
                expired = 0
                for token, cmd in list(_command_queue.items()):
                    if cmd and cmd.get("status") == "pending":
                        age = now - cmd.get("queued_at", now)
                        if age > CMD_TTL:
                            _command_queue[token] = None
                            expired += 1
                if expired:
                    app.logger.info(f"[CLEANUP] Expired {expired} stale command(s)")

                # Remove empty tables (no seats, last update > 5 min ago)
                stale_tables = [
                    tid for tid, t in _tables.items()
                    if not t["seats"] and (now - t["last_ts"]) > 300
                ]
                for tid in stale_tables:
                    del _tables[tid]
                    app.logger.info(f"[CLEANUP] Removed empty table {tid}")

        except Exception as e:
            app.logger.warning(f"[CLEANUP] Error: {e}")

# ── Endpoint 1: POST /api/snapshot ────────────────────────────────────────────

@app.route('/api/snapshot', methods=['POST'])
@limiter.limit("60 per minute")   # 1/sec per IP — adjust if multiple players same IP
def post_snapshot():
    api_key = request.headers.get('X-API-Key')
    if api_key != TRACKER_API_KEY:
        return jsonify({'ok': False, 'error': 'Invalid API key'}), 401

    payload = request.get_json()
    if not payload:
        return jsonify({'ok': False, 'error': 'No payload'}), 400

    table_id = payload.get('table_id')
    if not table_id:
        return jsonify({'ok': False, 'error': 'Missing table_id'}), 400

    seats_raw = payload.get('seats', [])
    hero_seat = next((s for s in seats_raw if s.get('is_hero')), None)
    if not hero_seat:
        return jsonify({'ok': False, 'error': 'No hero seat found'}), 400

    # NEW: Extract bot identity
    bot_id = payload.get('bot_id')

    ts = time.time()
    cashout_cmd = None   # built outside lock, queued inside

    with _store_lock:
        table = get_or_create_table(table_id)

        # NEW: Update bot-seat mapping
        if bot_id and hero_seat:
            hero_seat_index = hero_seat.get('seat_index')
            if hero_seat_index is not None:
                update_bot_seat_mapping(bot_id, table_id, hero_seat_index)

        if ts < table["last_ts"]:
            return jsonify({'ok': True, 'ignored': 'stale'}), 200

        hand_key = make_hand_key(payload)
        if table["hand_key"] != hand_key:
            # Archive previous hand before resetting
            if table["hand_key"] is not None:
                _archive_hand(table)
            table["hand_key"]     = hand_key
            table["seat_map"]     = {}
            table["seats"]        = {}
            table["next_seat_no"] = 1

        table["street"]      = payload.get("street")
        table["pot_zar"]     = payload.get("pot_zar")
        table["board"]       = payload.get("board", {"flop": [], "turn": None, "river": None})
        table["variant"]     = payload.get("variant", "plo")
        table["dealer_seat"] = payload.get("dealer_seat")

        new_seats    = {}
        hero_seat_no = None

        for s in seats_raw:
            name_key = normalize_name(s.get("name")) or f"anon_{s.get('seat_index', id(s))}"
            if name_key not in table["seat_map"]:
                table["seat_map"][name_key] = table["next_seat_no"]
                table["next_seat_no"] += 1
            seat_no = table["seat_map"][name_key]
            new_seats[seat_no] = {
                "seat_no":    seat_no,
                "name":       s.get("name"),
                "stack_zar":  s.get("stack_zar"),
                "hole_cards": s.get("hole_cards", []),
                "status":     s.get("status", "empty"),
                "is_dealer":  s.get("is_dealer", False),
                "is_hero":    s.get("is_hero", False),
                "last_seen":  ts,
            }
            if s.get("is_hero"):
                hero_seat_no = seat_no

        table["seats"]         = new_seats
        table["last_ts"]       = ts
        table["state_version"] += 1

        token = generate_seat_token(table_id, hero_seat_no)

        # Cashout auto-trigger
        if token in _cashout_state:
            cashout_available = payload.get('cashout_available', False)
            _cashout_state[token]['available'] = cashout_available
            if _cashout_state[token]['requested'] and cashout_available:
                cashout_cmd = {
                    'id':        str(uuid.uuid4())[:8],
                    'type':      'cashout',
                    'amount':    None,
                    'queued_at': ts,
                    'status':    'pending',
                }
                _command_queue[token]              = cashout_cmd
                _cashout_state[token]['requested'] = False

    # Log outside lock
    if cashout_cmd:
        app.logger.info(f"[CASHOUT] Auto-queued table={table_id} seat_no={hero_seat_no}")

    return jsonify({
        'ok':         True,
        'seat_token': token,
        'seat_no':    hero_seat_no,
        'table_id':   table_id,
    })

# ── Endpoint 2: GET /api/commands/pending ─────────────────────────────────────

@app.route('/api/commands/pending', methods=['GET'])
def get_pending_command():
    token = request.args.get('token')
    if not token:
        return jsonify({'ok': False, 'error': 'Missing token'}), 400

    with _store_lock:
        cmd = _command_queue.get(token)
        if cmd and cmd.get('status') == 'pending':
            return jsonify({'ok': True, 'command': cmd})
        return jsonify({'ok': True, 'command': None})

# ── Endpoint 3: POST /api/commands/ack ────────────────────────────────────────

@app.route('/api/commands/ack', methods=['POST'])
def ack_command():
    payload = request.get_json()
    if not payload:
        return jsonify({'ok': False, 'error': 'No payload'}), 400

    token      = payload.get('token')
    command_id = payload.get('command_id')
    if not token or not command_id:
        return jsonify({'ok': False, 'error': 'Missing token or command_id'}), 400

    with _store_lock:
        cmd = _command_queue.get(token)
        if cmd and cmd.get('id') == command_id:
            cmd['status'] = 'acked'
            _command_queue[token] = None
            app.logger.info(f"[CMD] Acked command {command_id}")

    return jsonify({'ok': True})

# ── Endpoint 4: POST /api/commands/queue ──────────────────────────────────────

@app.route('/api/commands/queue', methods=['POST'])
def queue_command():
    payload = request.get_json()
    if not payload:
        return jsonify({'ok': False, 'error': 'No payload'}), 400

    table_id     = payload.get('table_id')
    command_type = payload.get('command_type')
    amount       = payload.get('amount')
    seat_no      = payload.get('seat_no')
    if seat_no is None:
        seat_no = payload.get('seat_index')

    if not all([table_id, seat_no is not None, command_type]):
        return jsonify({'ok': False, 'error': 'Missing required fields'}), 400

    token = generate_seat_token(table_id, seat_no)

    with _store_lock:
        table = _tables.get(table_id)
        if not table:
            return jsonify({'ok': False, 'error': 'Table not found'}), 404
        if int(seat_no) not in table["seats"]:
            return jsonify({'ok': False, 'error': 'Seat not connected'}), 404

        command_id = str(uuid.uuid4())[:8]
        _command_queue[token] = {
            'id':        command_id,
            'type':      command_type,
            'amount':    amount,
            'queued_at': time.time(),
            'status':    'pending',
        }

    app.logger.info(f"[CMD] Queued {command_type} cmd={command_id} table={table_id} seat={seat_no}")
    return jsonify({'ok': True, 'command_id': command_id})

# ── Endpoint 5: GET /api/table/<table_id> ─────────────────────────────────────

@app.route('/api/table/<table_id>', methods=['GET'])
def get_table(table_id):
    with _store_lock:
        if table_id == 'latest':
            if not _tables:
                return jsonify({'ok': False, 'error': 'No active tables'}), 404
            table = max(_tables.values(), key=lambda t: t['last_ts'])
        else:
            table = _tables.get(table_id)
            if not table:
                return jsonify({'ok': False, 'error': 'Table not found'}), 404
        view = _table_view(table)
    return jsonify({'ok': True, 'table': view})

# ── Endpoint: GET /api/table/latest ───────────────────────────────────────────

@app.route('/api/table/latest', methods=['GET'])
def table_latest():
    with _store_lock:
        if not _tables:
            return jsonify({
                'ok': True,
                'table': {
                    'table_id': 'waiting',
                    'street':   'WAITING',
                    'pot_zar':  0,
                    'board':    {'flop': [], 'turn': '', 'river': ''},
                    'seats': [
                        {
                            'seat_no': i, 'name': None, 'stack_zar': 0,
                            'hole_cards': [], 'status': 'empty',
                            'is_dealer': False, 'is_hero': False,
                            'last_seen': None, 'pending_cmd': None,
                        }
                        for i in range(1, 10)
                    ]
                }
            })
        table = max(_tables.values(), key=lambda t: t['last_ts'])
        view  = _table_view(table)
    return jsonify({'ok': True, 'table': view})

# ── Endpoint 6: GET /api/tables ───────────────────────────────────────────────

@app.route('/api/tables', methods=['GET'])
def list_tables():
    with _store_lock:
        tables = sorted(
            [_table_view(t) for t in _tables.values()],
            key=lambda t: t['last_updated'],
            reverse=True,
        )
    return jsonify({'ok': True, 'tables': tables})

# ── Endpoint 7: GET /api/health ───────────────────────────────────────────────

@app.route('/api/health', methods=['GET'])
def health():
    with _store_lock:
        n_tables = len(_tables)
        n_cmds   = sum(1 for c in _command_queue.values() if c and c.get('status') == 'pending')
    return jsonify({
        'ok':           True,
        'environment':  os.getenv('FLASK_ENV', 'production'),
        'version':      'remote-control-3.0',
        'timestamp':    datetime.utcnow().isoformat(),
        'active_tables': n_tables,
        'pending_cmds':  n_cmds,
    })


@app.route('/api/bots', methods=['GET'])
def get_bots():
    """
    Return all known bots with their seating status.
    Used by Bots Manager page.
    """
    with _store_lock:
        bots = []

        # Add all bots that have sent snapshots
        for bot_id, info in _bot_seats.items():
            last_seen_ago = time.time() - info["last_seen"]
            state = "running" if last_seen_ago < 30 else "stale"

            bots.append({
                "name": bot_id,
                "table_id": info["table_id"],
                "seat_index": info["seat_index"],
                "last_seen": info["last_seen"],
                "last_seen_ago": last_seen_ago,
                "state": state,
                "status": f"Seated at {info['table_id']} seat {info['seat_index']}"
            })

        # Add known containers that haven't sent snapshots yet
        for i in range(1, 10):
            bot_id = f"pokerbet-bot{i}"
            if bot_id not in _bot_seats:
                bots.append({
                    "name": bot_id,
                    "table_id": None,
                    "seat_index": None,
                    "last_seen": None,
                    "last_seen_ago": None,
                    "state": "unknown",
                    "status": "Not seated or not running"
                })

    return jsonify({"ok": True, "bots": bots})


# ══════════════════════════════════════════════════════════════════════════════
# Add this after the /api/health endpoint (around line 480)

@app.route('/api/status', methods=['GET'])
def status():
    """Detailed status endpoint with metrics"""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        uptime_seconds = time.time() - process.create_time()
    except Exception:
        memory_mb = 0
        uptime_seconds = 0
    
    with _store_lock:
        table_count = len(_tables)
        command_queue_size = sum(1 for c in _command_queue.values() if c and c.get('status') == 'pending')
        # Count total seats across all tables
        total_seats = sum(len(t.get('seats', {})) for t in _tables.values())
    
    return jsonify({
        'service': 'remote-control-api',
        'status': 'healthy',
        'version': 'remote-control-3.0',
        'uptime_seconds': uptime_seconds,
        'timestamp': time.time(),
        'memory_mb': round(memory_mb, 2),
        'table_count': table_count,
        'seat_count': total_seats,
        'command_queue_size': command_queue_size,
        'warning_count': 0,
        'error_count': 0,
        'warnings': [],
        'errors': []
    })


@app.route('/api/version', methods=['GET'])
def version():
    """Version endpoint"""
    return jsonify({
        'service': 'remote-control-api',
        'version': 'remote-control-3.0',
        'build': os.getenv('FLASK_ENV', 'production'),
        'timestamp': time.time()
    })
# ██  HAND HISTORY (multi-hand ASCII log)
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/hands/recent', methods=['GET'])
def hands_recent():
    """Return last N hands as ASCII text blocks.
    Each hand: hole cards, flop, turn, river (one line per street, cards only).
    Hands separated by '------------------------'."""
    limit = min(int(request.args.get('limit', 20)), HAND_HISTORY_MAX)
    with _hand_lock:
        hands = list(_hand_history[-limit:])
    return jsonify({
        'ok': True,
        'hands': hands,
        'count': len(hands),
    })


@app.route('/api/hands/clear', methods=['POST'])
def hands_clear():
    """Clear hand history."""
    with _hand_lock:
        _hand_history.clear()
    return jsonify({'ok': True})


# ██  HAND COLLECTOR
# ══════════════════════════════════════════════════════════════════════════════

VALIDATED_HANDS_DIR = Path('/opt/plo-equity/validated_hands')
VALIDATED_HANDS_DIR.mkdir(parents=True, exist_ok=True)
_COLLECTOR_HTML     = Path('/opt/plo-equity/hand-collector/index.html')
_COLLECTOR_SAVE_DIR = Path('/opt/plo-equity/hand-collector/saved_hands')
_COLLECTOR_SAVE_DIR.mkdir(parents=True, exist_ok=True)


@app.route('/collector')
@app.route('/collector/')
def collector_ui():
    if _COLLECTOR_HTML.exists():
        return send_file(str(_COLLECTOR_HTML), mimetype='text/html')
    return '<h2>Hand Collector UI not found at ' + str(_COLLECTOR_HTML) + '</h2>', 404


@app.route('/collector/save', methods=['POST'])
def collector_save():
    # P2 fix: disk write never touches _store_lock
    try:
        body = request.get_json(force=True) or {}
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    text = (body.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'Empty text'}), 400

    ts       = datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')
    filename = f'hand_{ts}.txt'
    filepath = _COLLECTOR_SAVE_DIR / filename
    filepath.write_text(text + chr(10), encoding='utf-8')   # no lock held
    return jsonify({'ok': True, 'file': str(filepath)}), 200


@app.route('/collector/meta', methods=['GET'])
def collector_meta():
    return jsonify({'save_dir': str(_COLLECTOR_SAVE_DIR)}), 200


@app.route('/api/collector/latest', methods=['GET'])

@app.route('/api/remote/status', methods=['GET'])
def remote_status():
    """Detailed remote control status with command queue and seat details"""
    now = time.time()
    
    with _store_lock:
        # Build command queue details
        command_details = []
        for token, cmd in _command_queue.items():
            if cmd and cmd.get('status') == 'pending':
                command_details.append({
                    'seat_token': token,
                    'command': cmd.get('command'),
                    'status': cmd.get('status'),
                    'queued_at': cmd.get('queued_at'),
                    'age_seconds': round(now - cmd.get('queued_at', now), 1) if cmd.get('queued_at') else 0,
                })
        
        # Sort by most recent
        command_details.sort(key=lambda c: c.get('queued_at', 0), reverse=True)
        
        # Build table details with seat info
        table_details = []
        for table_id, table in _tables.items():
            seats_info = []
            for seat_no, seat in table.get('seats', {}).items():
                seat_token = seat.get('token', '')
                pending_cmd = _command_queue.get(seat_token)
                
                seats_info.append({
                    'seat_no': seat_no,
                    'name': seat.get('name'),
                    'stack_zar': seat.get('stack_zar', 0),
                    'status': seat.get('status', 'empty'),
                    'is_hero': seat.get('is_hero', False),
                    'is_dealer': seat.get('is_dealer', False),
                    'has_token': bool(seat_token),
                    'pending_command': pending_cmd.get('command') if pending_cmd and pending_cmd.get('status') == 'pending' else None,
                })
            
            table_details.append({
                'table_id': table_id,
                'last_update': table.get('last_ts'),
                'age_seconds': round(now - table.get('last_ts', now), 1),
                'street': table.get('street', 'UNKNOWN'),
                'pot_zar': table.get('pot_zar', 0),
                'seat_count': len(table.get('seats', {})),
                'active_seats': sum(1 for s in seats_info if s['name'] or s['stack_zar'] > 0),
                'seats': seats_info,
            })
        
        # Sort tables by most recent activity
        table_details.sort(key=lambda t: t.get('last_update', 0), reverse=True)
        
        # Calculate stats
        total_tables = len(_tables)
        total_seats = sum(len(t.get('seats', {})) for t in _tables.values())
        active_commands = len(command_details)
        
    return jsonify({
        'service': 'remote-control',
        'status': 'healthy',
        'timestamp': now,
        'total_tables': total_tables,
        'total_seats': total_seats,
        'active_commands': active_commands,
        'commands': command_details[:20],  # Top 20 most recent
        'tables': table_details[:10],  # Top 10 most active tables with full details
    })

@app.route('/api/engine/status', methods=['GET'])
def engine_status():
    """Engine status endpoint - checks if equity engine is accessible"""
    engine_url = os.getenv('ENGINE_URL', 'http://127.0.0.1:3000')
    try:
        import requests
        response = requests.get(f'{engine_url}/api/health', timeout=2)
        if response.status_code == 200:
            engine_data = response.json()
            return jsonify({
                'service': 'equity-engine',
                'status': 'healthy',
                'engine_url': engine_url,
                'version': engine_data.get('version', 'unknown'),
                'timestamp': time.time(),
            })
        else:
            return jsonify({
                'service': 'equity-engine',
                'status': 'degraded',
                'engine_url': engine_url,
                'error': f'HTTP {response.status_code}',
                'timestamp': time.time(),
            })
    except Exception as e:
        return jsonify({
            'service': 'equity-engine',
            'status': 'offline',
            'engine_url': engine_url,
            'error': str(e),
            'timestamp': time.time(),
        })


@app.route('/api/collector/status', methods=['GET'])
def collector_status():
    """Collector/snapshot status endpoint with table activity metrics"""
    with _store_lock:
        tables_data = []
        now = time.time()
        
        for table_id, table in _tables.items():
            last_update = table.get('last_ts', 0)
            age_seconds = now - last_update if last_update else 0
            
            # Count active (non-empty) seats
            active_seats = sum(1 for seat in table.get('seats', {}).values() 
                             if seat.get('name') or seat.get('stack_zar', 0) > 0)
            
            tables_data.append({
                'table_id': table_id,
                'last_update': last_update,
                'age_seconds': round(age_seconds, 1),
                'street': table.get('street', 'UNKNOWN'),
                'seat_count': len(table.get('seats', {})),
                'active_seats': active_seats,
                'hand_key': table.get('hand_key', ''),
            })
        
        # Sort by most recent activity
        tables_data.sort(key=lambda t: t['last_update'], reverse=True)
        
        # Calculate overall stats
        total_tables = len(_tables)
        total_seats = sum(len(t.get('seats', {})) for t in _tables.values())
        active_tables = sum(1 for t in tables_data if t['age_seconds'] < 30)
        
    return jsonify({
        'service': 'collector',
        'status': 'healthy',
        'timestamp': now,
        'total_tables': total_tables,
        'active_tables': active_tables,  # Updated in last 30s
        'total_seats': total_seats,
        'tables': tables_data[:20],  # Return top 20 most recent
        'state_file': str(STATE_FILE),
    })
def collector_latest():
    candidates = list(VALIDATED_HANDS_DIR.glob('*.json')) + list(_COLLECTOR_SAVE_DIR.glob('*.txt'))
    if not candidates:
        return jsonify({'ok': False, 'error': 'no hands found'}), 404

    latest = max(candidates, key=lambda f: f.stat().st_mtime)

    try:
        content = latest.read_text(encoding='utf-8').strip()
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

    raw_text = ''
    meta     = {}

    if latest.suffix == '.json':
        try:
            rec   = json.loads(content)
            hole  = rec.get('hole_cards') or []
            flop  = rec.get('flop') or []
            turn  = rec.get('turn') or ''
            river = rec.get('river') or ''

            lines = [''.join(hole)] if hole else []
            if flop:  lines.append(''.join(flop)  if isinstance(flop,  list) else flop)
            if turn:  lines.append(''.join(turn)  if isinstance(turn,  list) else turn)
            if river: lines.append(''.join(river) if isinstance(river, list) else river)

            raw_text = chr(10).join(lines)
            meta = {
                'variant':    rec.get('variant', ''),
                'hole_cards': hole,
                'flop':       flop,
                'street':     rec.get('street', 'UNKNOWN'),
                'player':     rec.get('player_name', ''),
                'validated':  rec.get('valid', False),
                'ts':         rec.get('created_at', ''),
            }
        except (json.JSONDecodeError, KeyError):
            raw_text = content
    else:
        raw_text = content

    return jsonify({'ok': True, 'raw': raw_text, 'file': str(latest), **meta}), 200

# ══════════════════════════════════════════════════════════════════════════════
# ██  CASHOUT
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/cashout/request', methods=['POST'])
def request_cashout():
    payload = request.get_json()
    if not payload:
        return jsonify({'ok': False, 'error': 'No payload'}), 400

    table_id = payload.get('table_id')
    seat_no  = payload.get('seat_no') or payload.get('seat_index')
    if not all([table_id, seat_no is not None]):
        return jsonify({'ok': False, 'error': 'Missing table_id or seat_no'}), 400

    token = generate_seat_token(table_id, seat_no)

    with _store_lock:
        if token not in _cashout_state:
            _cashout_state[token] = {'requested': False, 'available': False}
        _cashout_state[token]['requested'] = True

    app.logger.info(f"[CASHOUT] Request queued table={table_id} seat_no={seat_no}")
    return jsonify({'ok': True, 'status': 'queued', 'seat_token': token})


@app.route('/api/cashout/status', methods=['GET'])
def cashout_status():
    token = request.args.get('token')
    if not token:
        return jsonify({'ok': False, 'error': 'Missing token'}), 400

    with _store_lock:
        state = _cashout_state.get(token, {'requested': False, 'available': False})

    return jsonify({'ok': True, 'state': state})



# ══════════════════════════════════════════════════════════════════════════════
# ██  AUTHENTICATION & AUTHORIZATION
# ══════════════════════════════════════════════════════════════════════════════

from flask_login import login_user, logout_user

@app.route('/login')
def login_page():
    return send_from_directory("static", "login.html")

@app.route('/change-password')
@login_required
def change_password_page():
    return send_from_directory("static", "change-password.html")

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json()
    if not data:
        return jsonify({'ok': False, 'error': 'No data provided'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'ok': False, 'error': 'Username and password required'}), 400

    user = User.authenticate(username, password)

    if not user:
        audit_logs.log_login_failed(username,
                         ip_address=request.remote_addr, user_agent=request.headers.get('User-Agent'))
        return jsonify({'ok': False, 'error': 'Invalid credentials'}), 401

    if not user.is_active:
        audit_logs.log_login_failed(user.username,
                         ip_address=request.remote_addr)
        return jsonify({'ok': False, 'error': 'Account inactive'}), 403

    login_user(user, remember=data.get('remember', False))
    audit_logs.log_login_success(user.username, user_id=user.id,
                     ip_address=request.remote_addr, user_agent=request.headers.get('User-Agent'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT must_change_password FROM users WHERE id = ?', (user.id,))
    row = cursor.fetchone()
    must_change = row[0] if row else 0
    conn.close()

    return jsonify({
        'ok': True,
        'user': {'id': user.id, 'username': user.username, 'role': user.role},
        'must_change_password': bool(must_change),
        'redirect': '/change-password' if must_change else '/shell'
    }), 200

@app.route('/api/auth/logout', methods=['POST'])
@login_required
def api_logout():
    audit_logs.log_logout(current_user.username, user_id=current_user.id,
                     ip_address=request.remote_addr)
    logout_user()
    return jsonify({'ok': True}), 200

@app.route('/api/auth/me', methods=['GET'])
@login_required
def api_me():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT must_change_password FROM users WHERE id = ?', (current_user.id,))
    row = cursor.fetchone()
    must_change = row[0] if row else 0
    conn.close()

    return jsonify({
        'ok': True,
        'user': {
            'id': current_user.id,
            'username': current_user.username,
            'role': current_user.role,
            'must_change_password': bool(must_change)
        }
    }), 200

@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def api_change_password():
    data = request.get_json()
    if not data:
        return jsonify({'ok': False, 'error': 'No data provided'}), 400

    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not current_password or not new_password:
        return jsonify({'ok': False, 'error': 'Both passwords required'}), 400

    if len(new_password) < 4:
        return jsonify({'ok': False, 'error': 'Password must be at least 4 characters'}), 400

    user, password_hash = User.get_by_username(current_user.username)
    if not check_password_hash(password_hash, current_password):
        log_user_activity(current_user.id, current_user.username, 'password_change_failed',
                         status='failure', ip_address=request.remote_addr,
                         details='incorrect current password')
        return jsonify({'ok': False, 'error': 'Current password incorrect'}), 401

    new_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET password_hash = ?, must_change_password = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                  (new_hash, current_user.id))
    conn.commit()
    conn.close()

    log_user_activity(current_user.id, current_user.username, 'password_changed',
                     status='success', ip_address=request.remote_addr)

    return jsonify({'ok': True, 'message': 'Password changed successfully'}), 200


# ── Startup ────────────────────────────────────────────────────────────────────

def _start_background_threads():
    for target, name in [
        (_persist_loop,  'state-persist'),
        (_cleanup_loop,  'seat-cleanup'),
    ]:
        t = threading.Thread(target=target, name=name, daemon=True)
        t.start()
        app.logger.info(f"[STARTUP] Background thread started: {name}")


# Load persisted state before accepting requests
_load_state()
_start_background_threads()

# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEMD SERVICE — recommended settings (P1 + P3 fixes)
# Update /etc/systemd/system/plo-equity.service:
#
# [Unit]
# Description=PLO Remote Table Control v3
# After=network.target
#
# [Service]
# User=plo
# WorkingDirectory=/opt/plo-equity
# EnvironmentFile=/opt/plo-equity/.env
# ExecStart=/opt/plo-equity/venv/bin/gunicorn \
#     -w 3 \
#     --timeout 60 \
#     --worker-class sync \
#     --bind 0.0.0.0:8080 \
#     app:app
# Restart=on-failure
# RestartSec=5
# StartLimitBurst=5
# StartLimitIntervalSec=60
# StandardOutput=journal
# StandardError=journal
#
# [Install]
# WantedBy=multi-user.target
# ══════════════════════════════════════════════════════════════════════════════
