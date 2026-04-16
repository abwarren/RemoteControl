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
CORS(app)

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
_store_lock    = threading.Lock()

# ── Static file serving ────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "remote.html")

@app.route("/n4p.js")
def n4p_script():
    resp = send_from_directory("static", "n4p.js")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

# ── Helpers ────────────────────────────────────────────────────────────────────

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


def _build_seats_list(table):
    out = []
    for seat in sorted(table["seats"].values(), key=lambda s: s["seat_no"]):
        token = generate_seat_token(table["table_id"], seat["seat_no"])
        cmd = _command_queue.get(token)
        pending_cmd = cmd["type"] if cmd and cmd.get("status") == "pending" else None
        out.append({**seat, "pending_cmd": pending_cmd})
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

    ts = time.time()
    cashout_cmd = None   # built outside lock, queued inside

    with _store_lock:
        table = get_or_create_table(table_id)

        if ts < table["last_ts"]:
            return jsonify({'ok': True, 'ignored': 'stale'}), 200

        hand_key = make_hand_key(payload)
        if table["hand_key"] != hand_key:
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
    seat_no      = payload.get('seat_no') or payload.get('seat_index')

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

# ══════════════════════════════════════════════════════════════════════════════
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
# Basketball Live Markets - PokerBet Selectors
# Add this to app_v3.py after line 100 (after helpers section)

POKERBET_SELECTORS = {
    "navigation": {
        "sports_menu": "nav.sports-nav",
        "basketball_link": "a[href*='basketball']",
        "live_tab": "button[data-tab='live']",
        "match_card": ".match-card",
    },
    "match_page": {
        "team_names": ".team-name",
        "score": ".live-score",
        "time_remaining": ".game-clock",
        "quarter": ".period-indicator",
    },
    "main_markets": {
        "moneyline": ".market-moneyline",
        "spread": ".market-spread",
        "total": ".market-total",
        "odds_button": "button.odds-btn",
    },
    "live_specific": {
        "next_team_to_score": ".market-next-score",
        "quarter_winner": ".market-quarter",
        "race_to_points": ".market-race",
    },
    "betslip": {
        "container": "#betslip",
        "selection": ".bet-selection",
        "stake_input": "input[name='stake']",
        "place_bet_btn": "button.place-bet",
        "confirm_btn": "button.confirm-bet",
        "odds_display": ".bet-odds",
        "potential_return": ".potential-return",
    },
    "player_props": {
        "points": ".prop-points",
        "rebounds": ".prop-rebounds",
        "assists": ".prop-assists",
        "three_pointers": ".prop-threes",
    },
    "urls": {
        "base": "https://www.pokerbet.co.za",
        "basketball": "/sports/basketball",
        "live": "/live",
    }
}
