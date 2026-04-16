#!/usr/bin/env python3
import json
import hashlib
from pathlib import Path
from datetime import datetime

TRAINING_DIR = Path("/home/ubuntu/data/training")
TRAINING_DIR.mkdir(parents=True, exist_ok=True)

def parse_ascii_hands(text):
    """
    Parse ASCII hands format.
    
    Expected:
    4c2hTsKs
    9s8dThTc
    Qd2c5sJd
    
    9h8h7c
    """
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    
    if len(lines) < 2:
        return {"error": "Need at least 2 lines (hands + board)"}
    
    # Last line is board
    board_line = lines[-1]
    hand_lines = lines[:-1]
    
    # Detect variant
    if not hand_lines:
        return {"error": "No hands found"}
    
    hand_len = len(hand_lines[0])
    variant_map = {8: "PLO4", 10: "PLO5", 12: "PLO6"}
    variant = variant_map.get(hand_len)
    
    if not variant:
        return {"error": f"Invalid hand length: {hand_len}"}
    
    # Parse hands
    hands = []
    for idx, line in enumerate(hand_lines):
        if len(line) != hand_len:
            return {"error": f"Hand {idx+1} has wrong length: {len(line)} vs {hand_len}"}
        cards = [line[i:i+2] for i in range(0, len(line), 2)]
        hands.append({
            "player": f"Player{idx+1}",
            "cards": cards,
            "cards_str": line,
            "is_hero": idx == 0  # First hand is hero
        })
    
    # Parse board
    board = [board_line[i:i+2] for i in range(0, len(board_line), 2)]
    
    # Determine street
    board_len = len(board)
    street_map = {3: "flop", 4: "turn", 5: "river"}
    street = street_map.get(board_len, "unknown")
    
    return {
        "ok": True,
        "variant": f"{variant}-{len(hands)}MAX",
        "hands": hands,
        "hero_hand": hands[0] if hands else None,
        "board": board,
        "board_str": board_line,
        "street": street,
        "num_players": len(hands)
    }

def detect_hero(hands):
    """Detect which hand is hero (first by default)"""
    for h in hands:
        if h.get('is_hero'):
            return h
    return hands[0] if hands else None

def generate_training_recommendation(parsed):
    """Generate training recommendation based on hand"""
    if not parsed.get('ok'):
        return {"error": parsed.get('error')}
    
    hero = parsed.get('hero_hand')
    board = parsed.get('board', [])
    street = parsed.get('street')
    
    if not hero:
        return {"error": "No hero hand"}
    
    # Simple recommendation logic (placeholder)
    cards = hero.get('cards', [])
    recommendation = {
        "hero_cards": cards,
        "board": board,
        "street": street,
        "action": "check",  # Placeholder
        "reason": "Training sample - manual review required",
        "confidence": 0.5
    }
    
    return {
        "ok": True,
        "recommendation": recommendation
    }

def save_training_sample(parsed, recommendation, label=None):
    """Save training sample"""
    sample_id = hashlib.md5(json.dumps(parsed, sort_keys=True).encode()).hexdigest()[:8]
    filename = TRAINING_DIR / f"sample_{sample_id}.json"
    
    sample = {
        "sample_id": sample_id,
        "parsed": parsed,
        "recommendation": recommendation,
        "label": label,
        "saved_at": datetime.utcnow().isoformat(),
        "created_at": datetime.utcnow().isoformat()
    }
    
    with open(filename, 'w') as f:
        json.dump(sample, f, indent=2)
    
    return {"ok": True, "sample_id": sample_id, "file": str(filename)}

def load_training_samples():
    """Load all training samples"""
    samples = []
    for f in sorted(TRAINING_DIR.glob("sample_*.json")):
        try:
            with open(f) as fp:
                samples.append(json.load(fp))
        except Exception as e:
            samples.append({"error": str(e), "file": str(f)})
    return samples
