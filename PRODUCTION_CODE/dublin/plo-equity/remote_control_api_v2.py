#!/usr/bin/env python3
"""
Remote Control API for Hero State Management (Agent 1)

Provides endpoints for:
- Reading hero state (locked contract)
- Queueing validated commands for bots
- Receiving hero-only snapshots from n4p.js

LOCKED CONTRACT - DO NOT MODIFY:
{
  "hero_detected": boolean,
  "hero_seat": int | null,
  "hero_cards": string[],
  "board_cards": string[],
  "street": string,
  "seated": boolean,
  "in_hand": boolean,
  "can_act": boolean,
  "allowed_actions": string[],
  "waiting_for_big_blind": boolean
}
"""

import os
import json
import time
from datetime import datetime
from flask import Blueprint, request, jsonify
from pathlib import Path


# Create Blueprint
remote_control_bp = Blueprint('remote_control', __name__, url_prefix='/api/remote-control')

# Paths
STATE_FILE = Path('/home/ubuntu/data/remote_control_test_state.json')
COMMAND_QUEUE_PATH = Path('/home/ubuntu/data/command_queue.json')

# Command queue storage
command_queue = []


def load_state():
    """Load bot state from disk"""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading state: {e}")
        return {}


def save_state(state):
    """Save bot state to disk"""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Error saving state: {e}")


def load_command_queue():
    """Load command queue from disk"""
    global command_queue
    try:
        if COMMAND_QUEUE_PATH.exists():
            with open(COMMAND_QUEUE_PATH, 'r') as f:
                command_queue = json.load(f)
    except Exception as e:
        print(f"Error loading command queue: {e}")
        command_queue = []


def save_command_queue():
    """Save command queue to disk"""
    try:
        COMMAND_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(COMMAND_QUEUE_PATH, 'w') as f:
            json.dump(command_queue, f, indent=2)
    except Exception as e:
        print(f"Error saving command queue: {e}")


def extract_hero_state(bot_data):
    """
    Extract hero state from bot data and conform to locked contract.
    
    Input can be either:
    - Legacy format: bot_data[bot_id][table_id] structure
    - New format: Direct hero state object
    """
    # Handle new format (direct hero state)
    if 'hero_detected' in bot_data:
        return {
            'hero_detected': bot_data.get('hero_detected', False),
            'hero_seat': bot_data.get('hero_seat'),
            'hero_cards': bot_data.get('hero_cards', []),
            'board_cards': bot_data.get('board_cards', []),
            'street': bot_data.get('street', 'unknown'),
            'seated': bot_data.get('seated', False),
            'in_hand': bot_data.get('in_hand', False),
            'can_act': bot_data.get('can_act', False),
            'allowed_actions': bot_data.get('allowed_actions', []),
            'waiting_for_big_blind': bot_data.get('waiting_for_big_blind', False)
        }
    
    # Handle legacy format (find first table with data)
    if not bot_data or not isinstance(bot_data, dict):
        return default_hero_state()
    
    # Find first table with data
    for table_id, table_data in bot_data.items():
        if not isinstance(table_data, dict):
            continue
            
        hero = table_data.get('hero', {})
        board = table_data.get('board', {})
        action_state = table_data.get('action_state', {})
        
        # Extract cards
        hero_cards = hero.get('hole_cards', [])
        board_cards = []
        if board.get('flop'):
            board_cards.extend(board['flop'])
        if board.get('turn'):
            board_cards.append(board['turn'])
        if board.get('river'):
            board_cards.append(board['river'])
        
        # Determine allowed actions
        allowed_actions = []
        if action_state.get('hero_to_act', False):
            if action_state.get('can_check', False):
                allowed_actions.append('check')
            if action_state.get('can_call', False):
                allowed_actions.append('call')
            if action_state.get('can_bet', False):
                allowed_actions.append('bet')
            if action_state.get('can_raise', False):
                allowed_actions.append('raise')
                allowed_actions.append('raise_max')
            # Fold is always available when it's hero's turn
            allowed_actions.append('fold')
        
        return {
            'hero_detected': bool(hero.get('seat_index') is not None),
            'hero_seat': hero.get('seat_index'),
            'hero_cards': hero_cards,
            'board_cards': board_cards,
            'street': table_data.get('street', 'unknown'),
            'seated': bool(hero.get('seat_index') is not None),
            'in_hand': table_data.get('hand_stage') == 'in_progress',
            'can_act': action_state.get('hero_to_act', False),
            'allowed_actions': allowed_actions,
            'waiting_for_big_blind': False  # TODO: Detect from state
        }
    
    return default_hero_state()


def default_hero_state():
    """Return default empty hero state"""
    return {
        'hero_detected': False,
        'hero_seat': None,
        'hero_cards': [],
        'board_cards': [],
        'street': 'unknown',
        'seated': False,
        'in_hand': False,
        'can_act': False,
        'allowed_actions': [],
        'waiting_for_big_blind': False
    }


# ==================== ENDPOINTS ====================

@remote_control_bp.route('/state/<bot_id>', methods=['GET'])
def get_hero_state(bot_id):
    """
    Get hero state for a specific bot (LOCKED CONTRACT).
    
    Returns:
    {
      "hero_detected": boolean,
      "hero_seat": int | null,
      "hero_cards": string[],
      "board_cards": string[],
      "street": string,
      "seated": boolean,
      "in_hand": boolean,
      "can_act": boolean,
      "allowed_actions": string[],
      "waiting_for_big_blind": boolean
    }
    """
    state = load_state()
    
    if bot_id not in state:
        return jsonify({
            'error': f'Bot {bot_id} not found'
        }), 404
    
    hero_state = extract_hero_state(state[bot_id])
    return jsonify(hero_state)


@remote_control_bp.route('/command', methods=['POST'])
def queue_command():
    """
    Queue a command for a bot to execute.
    
    Request body:
    {
        "bot_id": "bot_1",
        "command": "fold"
    }
    
    Validates command against allowed_actions before queuing.
    """
    data = request.get_json()
    
    if not data:
        return jsonify({
            'ok': False,
            'error': 'No JSON data provided'
        }), 400
    
    bot_id = data.get('bot_id')
    command = data.get('command')
    
    if not bot_id or not command:
        return jsonify({
            'ok': False,
            'error': 'Missing required fields: bot_id, command'
        }), 400
    
    # Load state and validate command
    state = load_state()
    
    if bot_id not in state:
        return jsonify({
            'ok': False,
            'error': f'Bot {bot_id} not found'
        }), 404
    
    hero_state = extract_hero_state(state[bot_id])
    
    # Validate command against allowed_actions
    if command not in hero_state.get('allowed_actions', []):
        return jsonify({
            'ok': False,
            'error': f'Command "{command}" not in allowed_actions: {hero_state.get("allowed_actions", [])}',
            'allowed_actions': hero_state.get('allowed_actions', [])
        }), 400
    
    # Queue command
    load_command_queue()
    command_entry = {
        'command_id': f'cmd_{int(time.time() * 1000)}_{bot_id}',
        'bot_id': bot_id,
        'command': command,
        'queued_at': datetime.utcnow().isoformat(),
        'status': 'queued'
    }
    
    command_queue.append(command_entry)
    save_command_queue()
    
    return jsonify({
        'ok': True,
        'queued': True,
        'command_id': command_entry['command_id']
    })


@remote_control_bp.route('/snapshot', methods=['POST'])
def receive_snapshot():
    """
    Receive hero-only snapshot from n4p.js.
    
    Accepts hero state data and stores it in consolidated state file.
    Updates allowed_actions based on detected buttons.
    """
    data = request.get_json()
    
    if not data:
        return jsonify({
            'ok': False,
            'error': 'No JSON data provided'
        }), 400
    
    bot_id = data.get('bot_id', 'bot_1')  # Default to bot_1 if not specified
    
    # Load current state
    state = load_state()
    
    # Update bot state with new snapshot
    # Support both direct hero state and nested structure
    if 'hero_detected' in data:
        # Direct hero state format
        state[bot_id] = {
            'hero_detected': data.get('hero_detected', False),
            'hero_seat': data.get('hero_seat'),
            'hero_cards': data.get('hero_cards', []),
            'board_cards': data.get('board_cards', []),
            'street': data.get('street', 'unknown'),
            'seated': data.get('seated', False),
            'in_hand': data.get('in_hand', False),
            'can_act': data.get('can_act', False),
            'allowed_actions': data.get('allowed_actions', []),
            'waiting_for_big_blind': data.get('waiting_for_big_blind', False),
            'last_update_ts': time.time(),
            'last_update_iso': datetime.utcnow().isoformat()
        }
    else:
        # Legacy nested structure
        state[bot_id] = data
    
    # Save updated state
    save_state(state)
    
    return jsonify({
        'ok': True,
        'bot_id': bot_id,
        'received_at': datetime.utcnow().isoformat()
    })


@remote_control_bp.route('/commands/<bot_id>', methods=['GET'])
def get_bot_commands(bot_id):
    """Get all queued commands for a specific bot (for bot polling)"""
    load_command_queue()
    
    bot_commands = [
        cmd for cmd in command_queue
        if cmd.get('bot_id') == bot_id and cmd.get('status') == 'queued'
    ]
    
    return jsonify({
        'ok': True,
        'bot_id': bot_id,
        'commands': bot_commands
    })


@remote_control_bp.route('/command/<command_id>/ack', methods=['POST'])
def acknowledge_command(command_id):
    """Mark a command as executed (called by bot after execution)"""
    load_command_queue()
    
    for cmd in command_queue:
        if cmd.get('command_id') == command_id:
            cmd['status'] = 'executed'
            cmd['executed_at'] = datetime.utcnow().isoformat()
            save_command_queue()
            
            return jsonify({
                'ok': True,
                'command_id': command_id,
                'status': 'executed'
            })
    
    return jsonify({
        'ok': False,
        'error': f'Command {command_id} not found'
    }), 404


@remote_control_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for remote control API"""
    state_exists = STATE_FILE.exists()
    state = load_state()
    bot_count = len(state)
    
    return jsonify({
        'ok': True,
        'service': 'remote_control_api_hero',
        'version': '2.0.0',
        'state_file_exists': state_exists,
        'bot_count': bot_count,
        'bots': list(state.keys()),
        'timestamp': datetime.utcnow().isoformat()
    })


# Initialize command queue on module load
load_command_queue()
