"""
PLO Remote Table Control - Flask Backend v2
- Canonical _tables state (replaces _snapshot_store + _merged_tables)
- Name-keyed seat_map (stable seat_no per hand)
- hand_key reset on new hand
- Cashout wired to seat_no, not seat_index
"""

import os
import sys
import time
import hmac
import hashlib
import threading
import uuid
from datetime import datetime
from pathlib import Path
import json
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

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

# ── Environment ────────────────────────────────────────────────────────────────

N4P_SEAT_SECRET = os.getenv('N4P_SEAT_SECRET', 'default_secret_change_me')
TRACKER_API_KEY = os.getenv('TRACKER_API_KEY', 'trk_default')

# ── In-memory stores ───────────────────────────────────────────────────────────

_tables        = {}   # key: table_id → canonical table state
_command_queue = {}   # key: seat_token → command dict or None
_cashout_state = {}   # key: seat_token → {requested, available}
_store_lock    = threading.Lock()

# ── Helpers ────────────────────────────────────────────────────────────────────

def normalize_name(name):
    if not name:
        return None
    return str(name).strip().lower()


def make_hand_key(payload):
    return f"{payload.get('table_id')}:{payload.get('dealer_seat')}:{payload.get('deal_id')}"


def generate_seat_token(table_id, seat_no):
    """HMAC token — now keyed on stable seat_no, not seat_index."""
    msg = f"{table_id}:{seat_no}".encode('utf-8')
    return hmac.new(N4P_SEAT_SECRET.encode('utf-8'), msg, hashlib.sha256).hexdigest()


def get_or_create_table(table_id):
    if table_id not in _tables:
        _tables[table_id] = {
            "table_id":      table_id,
            "hand_key":      None,
            "state_version": 0,
            "last_ts":       0,
            "seats":         {},   # seat_no → seat dict
            "seat_map":      {},   # normalised name → seat_no
            "next_seat_no":  1,
            "variant":       "plo",
            "street":        None,
            "pot_zar":       0,
            "board":         {"flop": [], "turn": None, "river": None},
            "dealer_seat":   None,
        }
    return _tables[table_id]


def _build_seats_list(table):
    """Return seats sorted by seat_no, with pending_cmd injected."""
    out = []
    for seat in sorted(table["seats"].values(), key=lambda s: s["seat_no"]):
        token = generate_seat_token(table["table_id"], seat["seat_no"])
        cmd = _command_queue.get(token)
        pending_cmd = cmd["type"] if cmd and cmd.get("status") == "pending" else None
        out.append({**seat, "pending_cmd": pending_cmd})
    return out


def _table_view(table):
    """Serialise a canonical table for API responses."""
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

# ── Endpoint 1: POST /api/snapshot ────────────────────────────────────────────

@app.route('/api/snapshot', methods=['POST'])
def post_snapshot():
    """Receive snapshot from player browser, return seat token."""

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

    # Find hero seat
    hero_seat = next((s for s in seats_raw if s.get('is_hero')), None)
    if not hero_seat:
        return jsonify({'ok': False, 'error': 'No hero seat found'}), 400

    ts = time.time()

    with _store_lock:
        table = get_or_create_table(table_id)

        # Stale check
        if ts < table["last_ts"]:
            return jsonify({'ok': True, 'ignored': 'stale'}), 200

        hand_key = make_hand_key(payload)

        # New hand — reset seat assignments
        if table["hand_key"] != hand_key:
            table["hand_key"]     = hand_key
            table["seat_map"]     = {}
            table["seats"]        = {}
            table["next_seat_no"] = 1

        # Update table-level fields
        table["street"]      = payload.get("street")
        table["pot_zar"]     = payload.get("pot_zar")
        table["board"]       = payload.get("board", {"flop": [], "turn": None, "river": None})
        table["variant"]     = payload.get("variant", "plo")
        table["dealer_seat"] = payload.get("dealer_seat")

        # Merge seats
        new_seats = {}
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

        table["seats"]        = new_seats
        table["last_ts"]      = ts
        table["state_version"] += 1

        # Token is now keyed on stable seat_no
        token = generate_seat_token(table_id, hero_seat_no)

        # Cashout auto-trigger
        if token in _cashout_state:
            cashout_available = payload.get('cashout_available', False)
            _cashout_state[token]['available'] = cashout_available
            if _cashout_state[token]['requested'] and cashout_available:
                command_id = str(uuid.uuid4())[:8]
                _command_queue[token] = {
                    'id':        command_id,
                    'type':      'cashout',
                    'amount':    None,
                    'queued_at': time.time(),
                    'status':    'pending',
                }
                _cashout_state[token]['requested'] = False
                print(f'[CASHOUT] Auto-queued for table {table_id} seat_no {hero_seat_no}')

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

    return jsonify({'ok': True})

# ── Endpoint 4: POST /api/commands/queue ──────────────────────────────────────

@app.route('/api/commands/queue', methods=['POST'])
def queue_command():
    """Queue command from control panel. Accepts seat_no (preferred) or seat_index (legacy)."""
    payload = request.get_json()
    if not payload:
        return jsonify({'ok': False, 'error': 'No payload'}), 400

    table_id     = payload.get('table_id')
    command_type = payload.get('command_type')
    amount       = payload.get('amount')

    # Accept seat_no (new) or fall back to seat_index (legacy callers)
    seat_no = payload.get('seat_no') or payload.get('seat_index')

    if not all([table_id, seat_no is not None, command_type]):
        return jsonify({'ok': False, 'error': 'Missing required fields'}), 400

    token = generate_seat_token(table_id, seat_no)

    with _store_lock:
        table = _tables.get(table_id)
        if not table:
            return jsonify({'ok': False, 'error': 'Table not found'}), 404

        # Verify seat exists
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
        view = _table_view(table)

    return jsonify({'ok': True, 'table': view})

# ── Endpoint 6: GET /api/tables ───────────────────────────────────────────────

@app.route('/api/tables', methods=['GET'])
def list_tables():
    with _store_lock:
        tables = sorted(
            [_table_view(t) for t in _tables.values()],
            key=lambda t: t['last_updated'],
            reverse=True
        )
    return jsonify({'ok': True, 'tables': tables})

# ── Endpoint 7: GET /api/health ───────────────────────────────────────────────

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'ok':          True,
        'environment': os.getenv('FLASK_ENV', 'production'),
        'version':     'remote-control-2.0',
        'timestamp':   datetime.utcnow().isoformat(),
    })

# ══════════════════════════════════════════════════════════════════════════════
# ██  HAND COLLECTOR  —  /collector/*  and  /api/collector/*
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
    filepath.write_text(text + chr(10), encoding='utf-8')
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
                'variant':   rec.get('variant', ''),
                'hole_cards': hole,
                'flop':      flop,
                'street':    rec.get('street', 'UNKNOWN'),
                'player':    rec.get('player_name', ''),
                'validated': rec.get('valid', False),
                'ts':        rec.get('created_at', ''),
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
    seat_no  = payload.get('seat_no') or payload.get('seat_index')  # legacy compat

    if not all([table_id, seat_no is not None]):
        return jsonify({'ok': False, 'error': 'Missing table_id or seat_no'}), 400

    token = generate_seat_token(table_id, seat_no)

    with _store_lock:
        if token not in _cashout_state:
            _cashout_state[token] = {'requested': False, 'available': False}
        _cashout_state[token]['requested'] = True
        print(f'[CASHOUT] Request queued for table {table_id} seat_no {seat_no}')

    return jsonify({'ok': True, 'status': 'queued', 'seat_token': token})


@app.route('/api/cashout/status', methods=['GET'])
def cashout_status():
    token = request.args.get('token')
    if not token:
        return jsonify({'ok': False, 'error': 'Missing token'}), 400

    with _store_lock:
        state = _cashout_state.get(token, {'requested': False, 'available': False})

    return jsonify({'ok': True, 'state': state})


# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
