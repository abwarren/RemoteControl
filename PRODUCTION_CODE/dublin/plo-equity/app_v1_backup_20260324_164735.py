#!/usr/bin/env python3
"""
PLO Remote Table Control - Flask Backend
Endpoints for snapshot collection, command queuing, and table merging
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
CORS(app)  # Enable CORS for all routes (n4p.js runs on different domain)

# Static file serving
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

# Environment variables
N4P_SEAT_SECRET = os.getenv('N4P_SEAT_SECRET', 'default_secret_change_me')
TRACKER_API_KEY = os.getenv('TRACKER_API_KEY', 'trk_default')

# In-memory data stores
# Normalized table state storage_tables = {}  # key: table_id → canonical table state_command_queue = {}  # key: seat_token → command dict_cashout_state = {}  # key: seat_token → cashout state_store_lock = threading.Lock()
_cashout_state = {}  # key: seat_token, value: {requested: bool, available: bool}

# Helper: Generate deterministic seat token
def generate_seat_token(table_id, seat_index):
    """Generate HMAC-based seat token (deterministic per table+seat)"""
    msg = f"{table_id}:{seat_index}".encode('utf-8')
    return hmac.new(N4P_SEAT_SECRET.encode('utf-8'), msg, hashlib.sha256).hexdigest()

# Helper: Merge all seat snapshots for a table
def merge_table(table_id):
    """Build merged table view from all seat snapshots"""
    now = time.time()

    # Collect all seats for this table
    seat_records = []
    for store_key, record in _snapshot_store.items():
        if record['table_id'] == table_id:
            seat_records.append(record)

    if not seat_records:
        return None

    # Use most recent snapshot for table-level data
    latest_record = max(seat_records, key=lambda r: r['last_seen'])
    snap = latest_record['last_snapshot']

    # Build merged seats list
    seats_dict = {}
    for record in seat_records:
        seat_idx = record['seat_index']
        snap_seat = None

        # Find this seat in the snapshot
        for s in record['last_snapshot']['seats']:
            if s['seat_index'] == seat_idx:
                snap_seat = s
                break

        if snap_seat:
            # Check for pending command
            pending_cmd = None
            cmd = _command_queue.get(record['seat_token'])
            if cmd and cmd.get('status') == 'pending':
                pending_cmd = cmd['type']

            seats_dict[seat_idx] = {
                'seat_index': seat_idx,
                'name': snap_seat.get('name') or f"Seat {seat_idx}",
                'stack_zar': snap_seat.get('stack_zar'),
                'hole_cards': snap_seat.get('hole_cards', []),
                'status': snap_seat.get('status', 'empty'),
                'is_dealer': snap_seat.get('is_dealer', False),
                'has_token': True,
                'last_seen_ago': now - record['last_seen'],
                'pending_cmd': pending_cmd,
            }

    # Fill in empty seats from any snapshot (table structure)
    for s in snap.get('seats', []):
        if s['seat_index'] not in seats_dict:
            seats_dict[s['seat_index']] = {
                'seat_index': s['seat_index'],
                'name': s.get('name') or f"Seat {s['seat_index']}",
                'stack_zar': s.get('stack_zar'),
                'hole_cards': [],
                'status': s.get('status', 'empty'),
                'is_dealer': s.get('is_dealer', False),
                'has_token': False,
                'last_seen_ago': None,
                'pending_cmd': None,
            }

    # Sort seats by index
    sorted_seats = sorted(seats_dict.values(), key=lambda s: s['seat_index'])

    merged = {
        'table_id': table_id,
        'variant': snap.get('variant', 'plo'),
        'street': snap.get('street', 'PREFLOP'),
        'pot_zar': snap.get('pot_zar'),
        'dealer_seat': snap.get('dealer_seat'),
        'board': snap.get('board', {'flop': [], 'turn': None, 'river': None}),
        'last_updated': now,
        'seats': sorted_seats,
    }

    return merged

# Endpoint 1: POST /api/snapshot
@app.route('/api/snapshot', methods=['POST'])
def post_snapshot():
    """Receive snapshot from player browser, return seat token"""

    # Auth check
    api_key = request.headers.get('X-API-Key')
    if api_key != TRACKER_API_KEY:
        return jsonify({'ok': False, 'error': 'Invalid API key'}), 401

    payload = request.get_json()
    if not payload:
        return jsonify({'ok': False, 'error': 'No payload'}), 400

    table_id = payload.get('table_id')
    seats = payload.get('seats', [])

    if not table_id:
        return jsonify({'ok': False, 'error': 'Missing table_id'}), 400

    # Find hero seat
    hero_seat = None
    for s in seats:
        if s.get('is_hero'):
            hero_seat = s
            break

    if not hero_seat:
        return jsonify({'ok': False, 'error': 'No hero seat found'}), 400

    seat_index = hero_seat['seat_index']
    store_key = f"{table_id}:{seat_index}"
    timestamp = time.time()

    with _store_lock:
        # Generate seat token
        token = generate_seat_token(table_id, seat_index)

        # Store/update seat record
        _snapshot_store[store_key] = {
            'seat_token': token,
            'table_id': table_id,
            'seat_index': seat_index,
            'last_snapshot': payload,
            'last_seen': timestamp,
            'status': hero_seat.get('status', 'playing'),
            'name': hero_seat.get('name', f"Seat {seat_index}"),
            'stack_zar': hero_seat.get('stack_zar'),
        }

        # Rebuild merged table
        # Check cashout state and auto-trigger if requested + available        if token in _cashout_state:            # Extract cashout availability from snapshot (add to n4p.js later)            cashout_available = payload.get('cashout_available', False)            _cashout_state[token]['available'] = cashout_available                        # If cashout requested AND available, queue command            if _cashout_state[token]['requested'] and cashout_available:                command_id = str(uuid.uuid4())[:8]                _command_queue[token] = {                    'id': command_id,                    'type': 'cashout',                    'amount': None,                    'queued_at': time.time(),                    'status': 'pending',                }                _cashout_state[token]['requested'] = False                print(f'[CASHOUT] Auto-queued for table {table_id} seat {seat_index}')
        _merged_tables[table_id] = merge_table(table_id)

    return jsonify({
        'ok': True,
        'seat_token': token,
        'seat_index': seat_index,
        'table_id': table_id,
    })

# Endpoint 2: GET /api/commands/pending
@app.route('/api/commands/pending', methods=['GET'])
def get_pending_command():
    """Poll for pending commands (token-based auth)"""
    token = request.args.get('token')

    if not token:
        return jsonify({'ok': False, 'error': 'Missing token'}), 400

    with _store_lock:
        cmd = _command_queue.get(token)
        if cmd and cmd.get('status') == 'pending':
            return jsonify({'ok': True, 'command': cmd})
        else:
            return jsonify({'ok': True, 'command': None})

# Endpoint 3: POST /api/commands/ack
@app.route('/api/commands/ack', methods=['POST'])
def ack_command():
    """Acknowledge command execution"""
    payload = request.get_json()
    if not payload:
        return jsonify({'ok': False, 'error': 'No payload'}), 400

    token = payload.get('token')
    command_id = payload.get('command_id')

    if not token or not command_id:
        return jsonify({'ok': False, 'error': 'Missing token or command_id'}), 400

    with _store_lock:
        cmd = _command_queue.get(token)
        if cmd and cmd.get('id') == command_id:
            cmd['status'] = 'acked'
            _command_queue[token] = None  # Clear after ack

    return jsonify({'ok': True})

# Endpoint 4: POST /api/commands/queue
@app.route('/api/commands/queue', methods=['POST'])
def queue_command():
    """Queue command from control panel"""
    payload = request.get_json()
    if not payload:
        return jsonify({'ok': False, 'error': 'No payload'}), 400

    table_id = payload.get('table_id')
    seat_index = payload.get('seat_index')
    command_type = payload.get('command_type')
    amount = payload.get('amount')  # Optional: for raise commands

    if not all([table_id, seat_index is not None, command_type]):
        return jsonify({'ok': False, 'error': 'Missing required fields'}), 400

    # Generate token for this seat
    token = generate_seat_token(table_id, seat_index)
    store_key = f"{table_id}:{seat_index}"

    with _store_lock:
        # Check if seat exists
        if store_key not in _snapshot_store:
            return jsonify({'ok': False, 'error': 'Seat not connected'}), 404

        # Queue command
        command_id = str(uuid.uuid4())[:8]
        _command_queue[token] = {
            'id': command_id,
            'type': command_type,
            'amount': amount,
            'queued_at': time.time(),
            'status': 'pending',
        }

        # Refresh merged table
        _merged_tables[table_id] = merge_table(table_id)

    return jsonify({'ok': True, 'command_id': command_id})

# Endpoint 5: GET /api/table/<table_id>
@app.route('/api/table/<table_id>', methods=['GET'])
def get_table(table_id):
    """Get merged table view"""
    with _store_lock:
        if table_id == 'latest':
            # Get most recently updated table
            if not _merged_tables:
                return jsonify({'ok': False, 'error': 'No active tables'}), 404
            table = max(_merged_tables.values(), key=lambda t: t['last_updated'])
        else:
            table = _merged_tables.get(table_id)
            if not table:
                return jsonify({'ok': False, 'error': 'Table not found'}), 404

    return jsonify({'ok': True, 'table': table})

# Endpoint for remote control - returns latest table or stub
@app.route('/api/table/latest', methods=['GET'])
def table_latest():
    """Get latest table or return stub for remote control"""
    with _store_lock:
        if not _merged_tables:
            # Return stub when no active tables (for remote control)
            # Return stub with 9 empty seats for remote control
            return jsonify({
                'ok': True,
                'table': {
                    'table_id': 'waiting',
                    'street': 'WAITING',
                    'pot_zar': 0,
                    'board': {'flop': [], 'turn': '', 'river': ''},
                    'seats': [
                        {'seat_index': i, 'name': None, 'stack_zar': 0, 'hole_cards': [], 
                         'status': 'empty', 'is_dealer': False, 'has_token': False, 
                         'last_seen_ago': None, 'pending_cmd': None}
                        for i in range(1, 10)
                    ]
                }
            })
        # Get most recently updated table
        table = max(_merged_tables.values(), key=lambda t: t['last_updated'])
    return jsonify({'ok': True, 'table': table})

# Endpoint 6: GET /api/tables
@app.route('/api/tables', methods=['GET'])
def list_tables():
    """List all active tables"""
    with _store_lock:
        tables = list(_merged_tables.values())
        tables.sort(key=lambda t: t['last_updated'], reverse=True)

    return jsonify({'ok': True, 'tables': tables})

# Endpoint 7: GET /api/health
@app.route('/api/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'ok': True,
        'environment': os.getenv('FLASK_ENV', 'production'),
        'version': 'remote-control-1.0',
        'timestamp': datetime.utcnow().isoformat(),
    })

# ══════════════════════════════════════════════════════════════════════════════
# ██  HAND COLLECTOR  —  /collector/*  and  /api/collector/*
# ══════════════════════════════════════════════════════════════════════════════

VALIDATED_HANDS_DIR = Path('/opt/plo-equity/validated_hands')
VALIDATED_HANDS_DIR.mkdir(parents=True, exist_ok=True)
_COLLECTOR_HTML = Path('/opt/plo-equity/hand-collector/index.html')
_COLLECTOR_SAVE_DIR = Path('/opt/plo-equity/hand-collector/saved_hands')
_COLLECTOR_SAVE_DIR.mkdir(parents=True, exist_ok=True)


@app.route('/collector')
@app.route('/collector/')
def collector_ui():
    """Serve the hand-collector single-page UI."""
    if _COLLECTOR_HTML.exists():
        return send_file(str(_COLLECTOR_HTML), mimetype='text/html')
    return '<h2>Hand Collector UI not found at ' + str(_COLLECTOR_HTML) + '</h2>', 404


@app.route('/collector/save', methods=['POST'])
def collector_save():
    """Save raw hand text posted from the collector UI."""
    try:
        body = request.get_json(force=True) or {}
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    text = (body.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'Empty text'}), 400

    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')
    filename = f'hand_{ts}.txt'
    filepath = _COLLECTOR_SAVE_DIR / filename
    filepath.write_text(text + chr(10), encoding='utf-8')
    return jsonify({'ok': True, 'file': str(filepath)}), 200


@app.route('/collector/meta', methods=['GET'])
def collector_meta():
    """Return save directory path (used by collector UI on load)."""
    return jsonify({'save_dir': str(_COLLECTOR_SAVE_DIR)}), 200


@app.route('/api/collector/latest', methods=['GET'])
def collector_latest():
    """
    Return the most recent validated or saved hand as engine-ready text.

    Searches (newest-first):
      1. validated_hands/*.json  (tracker pipeline)
      2. hand-collector/saved_hands/*.txt  (manual save pipeline)

    Response:
      { ok, raw, file, variant, hole_cards, flop, street, player, ts }
    """
    candidates = list(VALIDATED_HANDS_DIR.glob('*.json')) + list(_COLLECTOR_SAVE_DIR.glob('*.txt'))

    if not candidates:
        return jsonify({'ok': False, 'error': 'no hands found'}), 404

    latest = max(candidates, key=lambda f: f.stat().st_mtime)

    try:
        content = latest.read_text(encoding='utf-8').strip()
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

    raw_text = ''
    meta = {}
    if latest.suffix == '.json':
        try:
            rec = json.loads(content)
            hole = rec.get('hole_cards') or []
            flop = rec.get('flop') or []
            turn = rec.get('turn') or ''
            river = rec.get('river') or ''

            lines = [''.join(hole)] if hole else []
            if flop:
                lines.append(''.join(flop) if isinstance(flop, list) else flop)
            if turn:
                lines.append(''.join(turn) if isinstance(turn, list) else turn)
            if river:
                lines.append(''.join(river) if isinstance(river, list) else river)

            raw_text = chr(10).join(lines)
            meta = {
                'variant': rec.get('variant', ''),
                'hole_cards': hole,
                'flop': flop,
                'street': rec.get('street', 'UNKNOWN'),
                'player': rec.get('player_name', ''),
                'validated': rec.get('valid', False),
                'ts': rec.get('created_at', ''),
            }
        except (json.JSONDecodeError, KeyError):
            raw_text = content
    else:
        raw_text = content

    return jsonify({'ok': True, 'raw': raw_text, 'file': str(latest), **meta}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

# Cashout state management endpoints
_cashout_state = {}  # key: seat_token, value: {requested: bool, available: bool}

@app.route('/api/cashout/request', methods=['POST'])
def request_cashout():
    """Request cashout for a seat (from remote control or manual button)"""
    payload = request.get_json()
    if not payload:
        return jsonify({'ok': False, 'error': 'No payload'}), 400

    table_id = payload.get('table_id')
    seat_index = payload.get('seat_index')

    if not all([table_id, seat_index is not None]):
        return jsonify({'ok': False, 'error': 'Missing table_id or seat_index'}), 400

    # Generate token for this seat
    token = generate_seat_token(table_id, seat_index)

    with _store_lock:
        if token not in _cashout_state:
            _cashout_state[token] = {'requested': False, 'available': False}
        
        _cashout_state[token]['requested'] = True
        print(f'[CASHOUT] Request queued for table {table_id} seat {seat_index}')

    return jsonify({'ok': True, 'status': 'queued', 'seat_token': token})


@app.route('/api/cashout/status', methods=['GET'])
def cashout_status():
    """Get cashout state for debugging"""
    token = request.args.get('token')
    if not token:
        return jsonify({'ok': False, 'error': 'Missing token'}), 400

    with _store_lock:
        state = _cashout_state.get(token, {'requested': False, 'available': False})
    
    return jsonify({'ok': True, 'state': state})
