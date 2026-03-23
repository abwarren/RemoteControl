#!/usr/bin/env python3
"""
Example: Hero-Only Data Extraction and Aggregation

Demonstrates practical usage of the Hero-only modules.
"""

from pathlib import Path
from hero_only_extractor import HeroOnlyExtractor, extract_hero_batch
from hero_aggregator import HeroAggregator, aggregate_from_directory


def example_1_extract_from_snapshot():
    """Example 1: Extract Hero from a snapshot"""
    print("\n" + "="*70)
    print("EXAMPLE 1: Extract Hero from Snapshot")
    print("="*70)

    extractor = HeroOnlyExtractor(strict_mode=False)

    # Simulated snapshot from browser
    snapshot = {
        'table_id': 'pokerbet_table_123',
        'hand_id': 'hand_20260323_001',
        'timestamp_utc': '2026-03-23T12:30:00Z',
        'street': 'FLOP',
        'variant': 'plo5-9max',
        'board': {
            'flop': ['As', 'Kh', 'Qd'],
            'turn': None,
            'river': None,
        },
        'seats': [
            {
                'seat_index': 2,
                'name': 'MyUsername',
                'stack_zar': 15000,
                'hole_cards': ['Ac', 'Kc', 'Qc', 'Jc', 'Tc'],
                'is_hero': True,
                'status': 'playing',
            },
            {
                'seat_index': 3,
                'name': 'Opponent1',
                'stack_zar': 12000,
                'hole_cards': [],  # Face down
                'is_hero': False,
                'status': 'playing',
            },
            {
                'seat_index': 5,
                'name': 'Opponent2',
                'stack_zar': 8000,
                'hole_cards': [],  # Face down
                'is_hero': False,
                'status': 'folded',
            },
        ],
    }

    hero_data = extractor.extract_from_snapshot(snapshot)

    if hero_data:
        print(f"✓ Extracted Hero: {hero_data.player_name}")
        print(f"  Hole cards: {' '.join(hero_data.hole_cards)}")
        print(f"  Flop: {' '.join(hero_data.flop)}")
        print(f"  Stack: {hero_data.stack_zar:,.0f} ZAR")
        print(f"  Variant: {hero_data.variant}")
        print(f"  Validation: {'PASS' if extractor.validate_no_opponent_data(hero_data) else 'FAIL'}")
    else:
        print("✗ Failed to extract Hero")

    print(f"\nExtractor stats: {extractor.get_stats()}")


def example_2_aggregate_multiple_hands():
    """Example 2: Aggregate multiple Hero hands"""
    print("\n" + "="*70)
    print("EXAMPLE 2: Aggregate Multiple Hero Hands")
    print("="*70)

    from hero_only_extractor import HeroHandData

    # Create sample hands (normally extracted from real data)
    hands = [
        HeroHandData(
            hand_id='h1',
            timestamp='2026-03-23T10:00:00Z',
            player_name='MyUsername',
            hole_cards=['Ac', 'Kc', 'Qc', 'Jc', 'Tc'],
            flop=['As', 'Ks', 'Qs'],
            turn='Js',
            river='Ts',
            street='RIVER',
            variant='plo5-9max',
            stack_zar=15000,
            table_id='table_1',
            seat_index=2,
        ),
        HeroHandData(
            hand_id='h2',
            timestamp='2026-03-23T10:05:00Z',
            player_name='MyUsername',
            hole_cards=['Ad', 'Kd', 'Qd', 'Jd', 'Td'],
            flop=['2h', '3h', '4h'],
            turn=None,
            river=None,
            street='FLOP',
            variant='plo5-9max',
            stack_zar=14500,
            table_id='table_1',
            seat_index=2,
        ),
        HeroHandData(
            hand_id='h3',
            timestamp='2026-03-23T10:10:00Z',
            player_name='MyUsername',
            hole_cards=['Ah', 'Kh', 'Qh', 'Jh'],
            flop=['9s', '8s', '7s'],
            turn='6s',
            river=None,
            street='TURN',
            variant='plo4-9max',
            stack_zar=16000,
            table_id='table_2',
            seat_index=5,
        ),
    ]

    # Aggregate
    agg = HeroAggregator()
    agg.add_hands(hands)

    # Compute stats
    stats = agg.compute_stats()
    print(f"✓ Hero: {stats.player_name}")
    print(f"  Total hands: {stats.total_hands}")
    print(f"  Variants: {stats.hands_by_variant}")
    print(f"  Streets: {stats.hands_by_street}")
    print(f"  Avg stack: {stats.average_stack_zar:,.2f} ZAR")
    print(f"  Stack range: {stats.min_stack_zar:,.0f} - {stats.max_stack_zar:,.0f} ZAR")
    print(f"  Tables played: {stats.tables_played}")
    print(f"  Session duration: {stats.session_duration_minutes:.1f} minutes")

    # Get variant breakdown
    print("\n  Variant Breakdown:")
    breakdown = agg.get_variant_breakdown()
    for variant, data in breakdown.items():
        print(f"    {variant}: {data['hands']} hands, avg {data['avg_stack']:,.0f} ZAR")


def example_3_filter_and_analyze():
    """Example 3: Filter and analyze by criteria"""
    print("\n" + "="*70)
    print("EXAMPLE 3: Filter and Analyze by Criteria")
    print("="*70)

    from hero_only_extractor import HeroHandData

    # Create sample dataset with mixed variants
    hands = []
    for i in range(10):
        variant = 'plo5-9max' if i % 2 == 0 else 'plo4-9max'
        street = ['FLOP', 'TURN', 'RIVER'][i % 3]
        hands.append(HeroHandData(
            hand_id=f'h{i}',
            timestamp=f'2026-03-23T10:{i:02d}:00Z',
            player_name='MyUsername',
            hole_cards=['Ac', 'Kc', 'Qc', 'Jc', 'Tc'][:4 if variant == 'plo4-9max' else 5],
            flop=['As', 'Ks', 'Qs'],
            turn='Js' if street in ['TURN', 'RIVER'] else None,
            river='Ts' if street == 'RIVER' else None,
            street=street,
            variant=variant,
            stack_zar=10000 + (i * 500),
            table_id=f'table_{i % 3}',
            seat_index=2,
        ))

    agg = HeroAggregator()
    agg.add_hands(hands)

    print(f"✓ Total hands: {len(hands)}")

    # Filter by variant
    plo5_agg = agg.filter_by_variant('plo5-9max')
    plo5_stats = plo5_agg.compute_stats()
    print(f"\n  PLO5 Only:")
    print(f"    Hands: {plo5_stats.total_hands}")
    print(f"    Avg stack: {plo5_stats.average_stack_zar:,.0f} ZAR")

    plo4_agg = agg.filter_by_variant('plo4-9max')
    plo4_stats = plo4_agg.compute_stats()
    print(f"\n  PLO4 Only:")
    print(f"    Hands: {plo4_stats.total_hands}")
    print(f"    Avg stack: {plo4_stats.average_stack_zar:,.0f} ZAR")

    # Filter by street
    river_agg = agg.filter_by_street('RIVER')
    river_stats = river_agg.compute_stats()
    print(f"\n  River Only:")
    print(f"    Hands: {river_stats.total_hands}")
    print(f"    Variants: {river_stats.hands_by_variant}")

    # Get starting hand distribution
    print(f"\n  Top Starting Hands:")
    for cards, count in agg.get_starting_hand_distribution(top_n=5):
        print(f"    {cards}: {count} times")


def example_4_validate_no_opponent_leakage():
    """Example 4: Validate no opponent data leakage"""
    print("\n" + "="*70)
    print("EXAMPLE 4: Validate No Opponent Data Leakage")
    print("="*70)

    extractor = HeroOnlyExtractor(strict_mode=False)

    # Test case 1: Valid Hero-only data
    valid_snapshot = {
        'table_id': 'table_1',
        'seats': [
            {
                'seat_index': 0,
                'name': 'Hero',
                'hole_cards': ['Ac', 'Kc', 'Qc', 'Jc'],
                'is_hero': True,
            },
            {
                'seat_index': 1,
                'name': 'Opponent',
                'hole_cards': [],  # Face down
                'is_hero': False,
            },
        ],
    }

    print("Test 1: Valid Hero-only snapshot")
    result = extractor.extract_from_snapshot(valid_snapshot)
    if result and extractor.validate_no_opponent_data(valid_snapshot):
        print("  ✓ PASS - No opponent leakage")
    else:
        print("  ✗ FAIL")

    # Test case 2: Invalid - opponent has cards
    invalid_snapshot = {
        'table_id': 'table_2',
        'seats': [
            {
                'seat_index': 0,
                'name': 'Hero',
                'hole_cards': ['Ac', 'Kc', 'Qc', 'Jc'],
                'is_hero': True,
            },
            {
                'seat_index': 1,
                'name': 'Opponent',
                'hole_cards': ['Ad', 'Kd', 'Qd', 'Jd'],  # Opponent has cards!
                'is_hero': False,
            },
        ],
    }

    print("\nTest 2: Invalid - opponent has hole cards")
    if not extractor.validate_no_opponent_data(invalid_snapshot):
        print("  ✓ PASS - Correctly rejected opponent data")
        print(f"  Reason: {extractor.rejection_reasons[-1]}")
    else:
        print("  ✗ FAIL - Should have rejected")

    # Test case 3: Invalid - multiple heroes
    multi_hero_snapshot = {
        'table_id': 'table_3',
        'seats': [
            {
                'seat_index': 0,
                'name': 'Hero1',
                'hole_cards': ['Ac', 'Kc', 'Qc', 'Jc'],
                'is_hero': True,
            },
            {
                'seat_index': 1,
                'name': 'Hero2',
                'hole_cards': ['Ad', 'Kd', 'Qd', 'Jd'],
                'is_hero': True,  # Two heroes!
            },
        ],
    }

    print("\nTest 3: Invalid - multiple heroes")
    if not extractor.validate_no_opponent_data(multi_hero_snapshot):
        print("  ✓ PASS - Correctly rejected multiple heroes")
        print(f"  Reason: {extractor.rejection_reasons[-1]}")
    else:
        print("  ✗ FAIL - Should have rejected")


def example_5_batch_processing():
    """Example 5: Batch process validated hands"""
    print("\n" + "="*70)
    print("EXAMPLE 5: Batch Process Validated Hands")
    print("="*70)

    # Check if validated hands directory exists
    validated_dir = Path('/opt/plo-equity/validated_hands')

    if validated_dir.exists():
        print(f"Processing hands from: {validated_dir}")

        # Aggregate all hands
        agg = aggregate_from_directory(str(validated_dir))
        stats = agg.compute_stats()

        print(f"\n✓ Loaded {stats.total_hands} Hero hands")
        if stats.total_hands > 0:
            print(f"  Player: {stats.player_name}")
            print(f"  Variants: {stats.hands_by_variant}")
            print(f"  Time range: {stats.first_hand_time} to {stats.last_hand_time}")
            print(f"  Session: {stats.session_duration_minutes:.1f} minutes")

            # Export to file
            output_file = Path('/home/warrenabrahams/hand-collector/hero_session_export.json')
            agg.export_to_json_file(str(output_file))
            print(f"\n✓ Exported to: {output_file}")
        else:
            print("  (No hands found in directory)")
    else:
        print(f"Directory not found: {validated_dir}")
        print("(This example requires actual validated hand files)")


if __name__ == '__main__':
    print("\n" + "#"*70)
    print("# HERO-ONLY DATA EXTRACTION & AGGREGATION EXAMPLES")
    print("#"*70)

    try:
        example_1_extract_from_snapshot()
        example_2_aggregate_multiple_hands()
        example_3_filter_and_analyze()
        example_4_validate_no_opponent_leakage()
        example_5_batch_processing()

        print("\n" + "#"*70)
        print("# ALL EXAMPLES COMPLETED")
        print("#"*70 + "\n")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
