# Hero-Only Data Extraction & Aggregation

Strict Hero-only data processing with ZERO opponent leakage.

## Overview

This module provides:
1. **`hero_only_extractor.py`** - Extracts only Hero data from hand histories
2. **`hero_aggregator.py`** - Aggregates Hero statistics across hands
3. **`test_hero_only.py`** - Comprehensive validation tests

## Key Principles

✅ **ONLY Hero data** - identified via `selfPlayer`/`is_hero` flag
✅ **NO opponent data** - opponents with hidden cards excluded
✅ **NO guessing** - never infer opponent hole cards
✅ **Validation first** - detect and prevent opponent leakage
✅ **Aggregation purity** - Hero-only stats, no mixing

## Quick Start

### Extract Hero from Snapshot

```python
from hero_only_extractor import HeroOnlyExtractor

extractor = HeroOnlyExtractor(strict_mode=True)

# Snapshot from POST /api/snapshot
snapshot = {
    'table_id': 'table_1',
    'hand_id': 'hand_001',
    'timestamp_utc': '2026-03-23T12:00:00Z',
    'street': 'FLOP',
    'variant': 'plo5-9max',
    'board': {'flop': ['As', 'Kh', 'Qd'], 'turn': None, 'river': None},
    'seats': [
        {
            'seat_index': 2,
            'name': 'HeroPlayer',
            'stack_zar': 10000,
            'hole_cards': ['Ac', 'Kc', 'Qc', 'Jc', 'Tc'],
            'is_hero': True,  # ← REQUIRED
            'status': 'playing',
        },
        {
            'seat_index': 3,
            'name': 'Opponent1',
            'hole_cards': [],  # ← Face down, excluded
            'is_hero': False,
        },
    ],
}

hero_data = extractor.extract_from_snapshot(snapshot)
print(f"Hero: {hero_data.player_name}")
print(f"Cards: {hero_data.hole_cards}")
print(f"Valid: {extractor.validate_no_opponent_data(hero_data)}")
```

### Extract Hero from Tracker Payload

```python
# From Tampermonkey script (already Hero-only by design)
tracker_payload = {
    'hand_id': 'trk_001',
    'timestamp_utc': '2026-03-23T12:00:00Z',
    'player_name': 'Hero123',
    'hole_cards': ['Ac', 'Kc', 'Qc', 'Jc', 'Tc'],
    'flop': ['As', 'Ks', 'Qs'],
    'turn': 'Js',
    'river': None,
    'street': 'TURN',
    'variant': 'plo5-9max',
    'stack_zar': 12000,
}

hero_data = extractor.extract_from_tracker_payload(tracker_payload)
```

### Aggregate Hero Statistics

```python
from hero_aggregator import HeroAggregator

agg = HeroAggregator()
agg.add_hands([hero_data1, hero_data2, hero_data3])

# Compute stats
stats = agg.compute_stats()
print(f"Player: {stats.player_name}")
print(f"Total hands: {stats.total_hands}")
print(f"Variants: {stats.hands_by_variant}")
print(f"Avg stack: {stats.average_stack_zar:.2f} ZAR")
print(f"Win rate: {stats.win_rate}")

# Filter by variant
plo5_agg = agg.filter_by_variant('plo5-9max')
plo5_stats = plo5_agg.compute_stats()

# Get starting hand distribution
top_hands = agg.get_starting_hand_distribution(top_n=20)
for cards, count in top_hands:
    print(f"  {cards}: {count} times")

# Export to JSON
agg.export_to_json_file('/path/to/hero_stats.json')
```

### Batch Processing

```python
from hero_only_extractor import extract_hero_batch

# From validated hands directory
from pathlib import Path
validated_files = list(Path('/opt/plo-equity/validated_hands').glob('*.json'))

hero_hands = extract_hero_batch(validated_files)
print(f"Extracted {len(hero_hands)} Hero hands")

# Aggregate
agg = HeroAggregator()
agg.add_hands(hero_hands)
```

## Integration with Existing System

### Flask API Integration

```python
from flask import Flask, request, jsonify
from hero_only_extractor import HeroOnlyExtractor
from hero_aggregator import HeroAggregator, aggregate_from_directory

app = Flask(__name__)
extractor = HeroOnlyExtractor(strict_mode=False)

@app.route('/api/snapshot', methods=['POST'])
def post_snapshot():
    """Existing snapshot endpoint - add Hero extraction"""
    payload = request.get_json()

    # Extract Hero data
    hero_data = extractor.extract_from_snapshot(payload)

    if hero_data:
        # Save to validated_hands directory
        save_path = Path('/opt/plo-equity/validated_hands')
        save_path.mkdir(parents=True, exist_ok=True)

        hero_file = save_path / f"hero_{hero_data.hand_id}.json"
        hero_file.write_text(json.dumps(hero_data.to_dict(), indent=2))

    # ... existing snapshot logic ...
    return jsonify({'ok': True, 'hero_extracted': hero_data is not None})

@app.route('/api/hero/stats', methods=['GET'])
def get_hero_stats():
    """NEW: Get aggregated Hero statistics"""
    variant = request.args.get('variant')

    agg = aggregate_from_directory('/opt/plo-equity/validated_hands', variant=variant)
    stats = agg.compute_stats()

    return jsonify({
        'ok': True,
        'stats': stats.to_dict(),
        'top_hands': agg.get_starting_hand_distribution(top_n=20),
        'variant_breakdown': agg.get_variant_breakdown(),
    })

@app.route('/api/hero/session', methods=['GET'])
def get_hero_session():
    """NEW: Get Hero session data with filters"""
    variant = request.args.get('variant')
    start_date = request.args.get('start')
    end_date = request.args.get('end')

    agg = aggregate_from_directory('/opt/plo-equity/validated_hands', variant=variant)

    if start_date and end_date:
        agg = agg.filter_by_date_range(start_date, end_date)

    return jsonify({
        'ok': True,
        'data': agg.export_to_dict(),
    })
```

### Command Line Usage

```bash
# Run extraction on validated hands
cd /home/warrenabrahams/hand-collector
python3 -c "
from hero_aggregator import aggregate_from_directory
agg = aggregate_from_directory('/opt/plo-equity/validated_hands')
stats = agg.compute_stats()
print(f'Hero: {stats.player_name}')
print(f'Hands: {stats.total_hands}')
print(f'Variants: {stats.hands_by_variant}')
agg.export_to_json_file('hero_stats.json')
print('Exported to hero_stats.json')
"

# Run tests
python3 test_hero_only.py
```

## Validation & Safety

### Strict Mode

```python
# Strict mode - raises exceptions on invalid data
extractor = HeroOnlyExtractor(strict_mode=True)

# Lenient mode - logs warnings and continues
extractor = HeroOnlyExtractor(strict_mode=False)
stats = extractor.get_stats()
print(f"Extracted: {stats['extraction_count']}")
print(f"Rejected: {stats['rejection_count']}")
print(f"Reasons: {stats['recent_rejections']}")
```

### Opponent Data Detection

```python
# Validate no opponent leakage
if not extractor.validate_no_opponent_data(data):
    print("WARNING: Opponent data detected!")
    print(extractor.rejection_reasons[-1])
```

### Failure Cases Prevented

❌ Including players with `is_hero=False`
❌ Including opponents with hidden/facedown cards
❌ Mixing opponent stats into Hero aggregates
❌ Treating all players equally instead of filtering
❌ Multiple players claiming to be Hero
❌ Opponents with visible hole cards
❌ Duplicate cards (Hero + board overlap)

## Data Structure

### HeroHandData

```python
@dataclass
class HeroHandData:
    hand_id: str
    timestamp: str
    player_name: str
    hole_cards: List[str]      # 4-7 cards
    flop: List[str]            # 0 or 3 cards
    turn: Optional[str]
    river: Optional[str]
    street: str                # PREFLOP/FLOP/TURN/RIVER
    variant: str               # plo4-9max, plo5-9max, etc.
    stack_zar: float
    table_id: str
    seat_index: int
    actions: List[Dict]        # Future: Hero's actions
    final_pot: Optional[float]
    won_amount: Optional[float]
```

### HeroSessionStats

```python
@dataclass
class HeroSessionStats:
    player_name: str
    total_hands: int
    hands_by_variant: Dict[str, int]
    hands_by_street: Dict[str, int]
    hole_cards_frequency: Dict[str, int]
    total_stack_invested: float
    average_stack_zar: float
    max_stack_zar: float
    min_stack_zar: float
    total_won: float
    total_hands_with_result: int
    win_rate: Optional[float]
    first_hand_time: str
    last_hand_time: str
    session_duration_minutes: float
    tables_played: int
    hands_per_table: Dict[str, int]
```

## Testing

All 25 tests pass with 100% Hero isolation:

```bash
$ python3 test_hero_only.py
======================================================================
HERO-ONLY DATA EXTRACTION & AGGREGATION TEST SUITE
======================================================================

Running tests to verify:
  ✓ Hero identification via selfPlayer/is_hero flag
  ✓ No opponent data leakage
  ✓ Rejection of invalid/mixed data
  ✓ Correct aggregation of Hero-only stats
  ✓ Proper filtering and edge case handling

----------------------------------------------------------------------
Ran 25 tests in 0.001s

OK
```

## Files

- **`hero_only_extractor.py`** (413 lines) - Core extraction logic
- **`hero_aggregator.py`** (389 lines) - Aggregation and statistics
- **`test_hero_only.py`** (485 lines) - Comprehensive test suite
- **`HERO_ONLY_USAGE.md`** (this file) - Documentation

## License

Part of PLO Remote Control system.
