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
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes (n4p.js runs on different domain)

# Import and register collector routes
from collector_routes import register_collector_routes
register_collector_routes(app)

# Import and register equity engine routes
from equity_routes import register_equity_routes
register_equity_routes(app)

# Environment variables
N4P_SEAT_SECRET = os.getenv('N4P_SEAT_SECRET', 'default_secret_change_me')
TRACKER_API_KEY = os.getenv('TRACKER_API_KEY', 'trk_default')
COMMAND_TTL = int(os.getenv('COMMAND_TTL', '30'))  # Commands expire after 30 seconds

# In-memory data stores
_snapshot_store = {}  # key: "table_id:seat_no", value: seat record
_merged_tables = {}   # key: table_id, value: MergedTable dict
_command_queue = {}   # key: "table_id:seat_no", value: command dict or None
_store_lock = threading.Lock()

# Helper: Generate command queue key
def make_command_key(table_id, seat_no):
    """Generate command queue key from table_id and seat_no"""
    return f"{table_id}:{seat_no}"

# Helper: Clean expired commands
def clean_expired_commands():
    """Remove commands older than COMMAND_TTL seconds"""
    now = time.time()
    expired_keys = []

    for key, cmd in _command_queue.items():
        if cmd and cmd.get('queued_at'):
            age = now - cmd['queued_at']
            if age > COMMAND_TTL:
                expired_keys.append(key)

    for key in expired_keys:
        print(f"[TTL] Expired command: {_command_queue[key].get('type')} at {key}", flush=True)
        _command_queue[key] = None

    return len(expired_keys)

# Background thread: Clean expired commands periodically
def _cleanup_loop():
    """Background thread to clean expired commands every 10 seconds"""
    while True:
        time.sleep(10)
        with _store_lock:
            expired_count = clean_expired_commands()
            if expired_count > 0:
                print(f"[TTL] Cleaned {expired_count} expired commands", flush=True)

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
            cmd = _command_queue.get(record['command_key'])
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
        # Store/update seat record
        _snapshot_store[store_key] = {
            'command_key': store_key,  # Use table_id:seat_no as key
            'table_id': table_id,
            'seat_index': seat_index,
            'last_snapshot': payload,
            'last_seen': timestamp,
            'status': hero_seat.get('status', 'playing'),
            'name': hero_seat.get('name', f"Seat {seat_index}"),
            'stack_zar': hero_seat.get('stack_zar'),
        }

        # Rebuild merged table
        _merged_tables[table_id] = merge_table(table_id)

    return jsonify({
        'ok': True,
        'table_id': table_id,
        'seat_no': seat_index,
        'player_name': hero_seat.get('name'),
    })

# Endpoint 2: GET /api/commands/pending
@app.route('/api/commands/pending', methods=['GET'])
def get_pending_command():
    """Poll for pending commands using table_id + seat_no"""
    table_id = request.args.get('table_id')
    seat_no = request.args.get('seat_no')

    if not table_id or seat_no is None:
        return jsonify({'ok': False, 'error': 'Missing table_id or seat_no'}), 400

    key = make_command_key(table_id, int(seat_no))

    with _store_lock:
        # Clean expired commands before checking
        clean_expired_commands()

        cmd = _command_queue.get(key)
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

    table_id = payload.get('table_id')
    seat_no = payload.get('seat_no')
    command_id = payload.get('command_id')

    if not table_id or seat_no is None or not command_id:
        return jsonify({'ok': False, 'error': 'Missing table_id, seat_no, or command_id'}), 400

    key = make_command_key(table_id, int(seat_no))

    with _store_lock:
        cmd = _command_queue.get(key)
        if cmd and cmd.get('id') == command_id:
            cmd['status'] = 'acked'
            _command_queue[key] = None  # Clear after ack

    return jsonify({'ok': True})

# Endpoint 4: POST /api/commands/queue
@app.route('/api/commands/queue', methods=['POST'])
def queue_command():
    """Queue command from control panel"""
    payload = request.get_json()
    if not payload:
        return jsonify({'ok': False, 'error': 'No payload'}), 400

    table_id = payload.get('table_id')
    seat_no = payload.get('seat_no') or payload.get('seat_index')  # Support both names
    command_type = payload.get('command_type')

    if not all([table_id, seat_no is not None, command_type]):
        return jsonify({'ok': False, 'error': 'Missing required fields'}), 400

    key = make_command_key(table_id, int(seat_no))
    store_key = f"{table_id}:{seat_no}"

    with _store_lock:
        # Check if seat exists
        if store_key not in _snapshot_store:
            return jsonify({'ok': False, 'error': 'Seat not connected'}), 404

        # Queue command
        command_id = str(uuid.uuid4())[:8]
        _command_queue[key] = {
            'id': command_id,
            'type': command_type,
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
                        for i in range(9)
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

# Start background cleanup thread
def start_background_threads():
    """Start background threads for command cleanup"""
    cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True, name='command-cleanup')
    cleanup_thread.start()
    print(f"[STARTUP] Command TTL cleanup thread started (TTL={COMMAND_TTL}s)", flush=True)

# Start threads on import (when gunicorn loads the module)
start_background_threads()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
