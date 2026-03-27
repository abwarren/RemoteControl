#!/usr/bin/env python3
"""
Validation Tests for Hero-Only Extractor and Aggregator

Tests verify:
1. Hero identification via selfPlayer/is_hero flag
2. No opponent data leakage
3. Rejection of invalid/mixed data
4. Correct aggregation of Hero-only stats
5. Proper filtering and edge case handling
"""

import unittest
from datetime import datetime
from hero_only_extractor import HeroOnlyExtractor, HeroHandData, extract_hero_batch
from hero_aggregator import HeroAggregator


class TestHeroExtraction(unittest.TestCase):
    """Test Hero-only data extraction"""

    def setUp(self):
        """Set up test extractor"""
        self.extractor = HeroOnlyExtractor(strict_mode=True)

    def test_valid_snapshot_with_hero(self):
        """Test extraction from valid snapshot with is_hero flag"""
        snapshot = {
            'table_id': 'test_1',
            'hand_id': 'hand_001',
            'timestamp_utc': '2026-03-23T12:00:00Z',
            'street': 'FLOP',
            'variant': 'plo4-9max',
            'board': {'flop': ['As', 'Kh', 'Qd'], 'turn': None, 'river': None},
            'seats': [
                {
                    'seat_index': 2,
                    'name': 'HeroPlayer',
                    'stack_zar': 10000,
                    'hole_cards': ['Ac', 'Kc', 'Qc', 'Jc'],
                    'is_hero': True,
                    'status': 'playing',
                },
                {
                    'seat_index': 3,
                    'name': 'Villain1',
                    'stack_zar': 8000,
                    'hole_cards': [],  # Face down
                    'is_hero': False,
                },
            ],
        }

        result = self.extractor.extract_from_snapshot(snapshot)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, HeroHandData)
        self.assertEqual(result.player_name, 'HeroPlayer')
        self.assertEqual(len(result.hole_cards), 4)
        self.assertEqual(result.seat_index, 2)
        self.assertEqual(result.variant, 'plo4-9max')

    def test_no_hero_flag_rejection(self):
        """Test rejection when no seat has is_hero=True"""
        snapshot = {
            'table_id': 'test_2',
            'seats': [
                {
                    'seat_index': 0,
                    'name': 'Player1',
                    'hole_cards': ['As', 'Kh', 'Qd', 'Jc'],
                    'is_hero': False,  # Not Hero!
                },
            ],
        }

        with self.assertRaises(ValueError) as ctx:
            self.extractor.extract_from_snapshot(snapshot)

        self.assertIn('is_hero', str(ctx.exception))

    def test_hero_without_cards_rejection(self):
        """Test rejection when Hero has no hole cards"""
        snapshot = {
            'table_id': 'test_3',
            'seats': [
                {
                    'seat_index': 0,
                    'name': 'Hero',
                    'hole_cards': [],  # No cards!
                    'is_hero': True,
                },
            ],
        }

        with self.assertRaises(ValueError) as ctx:
            self.extractor.extract_from_snapshot(snapshot)

        self.assertIn('hole cards', str(ctx.exception).lower())

    def test_insufficient_hole_cards_rejection(self):
        """Test rejection when Hero has < 4 hole cards"""
        snapshot = {
            'table_id': 'test_4',
            'seats': [
                {
                    'seat_index': 0,
                    'name': 'Hero',
                    'hole_cards': ['As', 'Kh'],  # Only 2 cards!
                    'is_hero': True,
                },
            ],
        }

        with self.assertRaises(ValueError):
            self.extractor.extract_from_snapshot(snapshot)

    def test_duplicate_cards_rejection(self):
        """Test rejection when duplicate cards detected"""
        snapshot = {
            'table_id': 'test_5',
            'street': 'FLOP',
            'board': {'flop': ['As', 'Kh', 'Qd'], 'turn': None, 'river': None},
            'seats': [
                {
                    'seat_index': 0,
                    'name': 'Hero',
                    'hole_cards': ['As', 'Kh', 'Qc', 'Jc'],  # As and Kh also on board!
                    'is_hero': True,
                },
            ],
        }

        with self.assertRaises(ValueError) as ctx:
            self.extractor.extract_from_snapshot(snapshot)

        self.assertIn('Duplicate', str(ctx.exception))

    def test_tracker_payload_extraction(self):
        """Test extraction from tracker API payload"""
        payload = {
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
            'table_id': 'pokerbet_123',
        }

        result = self.extractor.extract_from_tracker_payload(payload)

        self.assertIsNotNone(result)
        self.assertEqual(result.player_name, 'Hero123')
        self.assertEqual(len(result.hole_cards), 5)
        self.assertEqual(result.variant, 'plo5-9max')
        self.assertEqual(result.turn, 'Js')
        self.assertIsNone(result.river)

    def test_opponent_data_validation_pass(self):
        """Test that Hero-only data passes opponent validation"""
        hero_data = HeroHandData(
            hand_id='h1',
            timestamp='2026-03-23T12:00:00Z',
            player_name='Hero',
            hole_cards=['Ac', 'Kc', 'Qc', 'Jc'],
            flop=['As', 'Ks', 'Qs'],
            turn=None,
            river=None,
            street='FLOP',
            variant='plo4-9max',
            stack_zar=10000,
            table_id='table_1',
            seat_index=2,
        )

        self.assertTrue(self.extractor.validate_no_opponent_data(hero_data))

    def test_opponent_data_validation_fail_multiple_heroes(self):
        """Test validation fails when multiple seats claim to be Hero"""
        snapshot = {
            'seats': [
                {
                    'seat_index': 0,
                    'name': 'Hero1',
                    'hole_cards': ['As', 'Kh', 'Qd', 'Jc'],
                    'is_hero': True,
                },
                {
                    'seat_index': 1,
                    'name': 'Hero2',
                    'hole_cards': ['Ac', 'Kc', 'Qc', 'Jh'],
                    'is_hero': True,  # Two heroes!
                },
            ],
        }

        self.assertFalse(self.extractor.validate_no_opponent_data(snapshot))

    def test_opponent_data_validation_fail_opponent_cards(self):
        """Test validation fails when opponent has hole cards"""
        snapshot = {
            'seats': [
                {
                    'seat_index': 0,
                    'name': 'Hero',
                    'hole_cards': ['As', 'Kh', 'Qd', 'Jc'],
                    'is_hero': True,
                },
                {
                    'seat_index': 1,
                    'name': 'Villain',
                    'hole_cards': ['Ac', 'Kc', 'Qc', 'Jh'],  # Opponent has cards!
                    'is_hero': False,
                },
            ],
        }

        self.assertFalse(self.extractor.validate_no_opponent_data(snapshot))

    def test_batch_extraction(self):
        """Test batch extraction from multiple sources"""
        sources = [
            {
                'table_id': 'table_1',
                'seats': [
                    {
                        'seat_index': 0,
                        'name': 'Hero',
                        'hole_cards': ['As', 'Kh', 'Qd', 'Jc'],
                        'is_hero': True,
                    },
                ],
            },
            {
                'hand_id': 'trk_001',
                'player_name': 'Hero',
                'hole_cards': ['Ac', 'Kc', 'Qc', 'Jc'],
                'flop': [],
                'variant': 'plo4-9max',
                'stack_zar': 10000,
            },
        ]

        results = extract_hero_batch(sources)

        self.assertEqual(len(results), 2)
        self.assertTrue(all(isinstance(r, HeroHandData) for r in results))


class TestHeroAggregation(unittest.TestCase):
    """Test Hero-only data aggregation"""

    def setUp(self):
        """Set up test aggregator with sample hands"""
        self.agg = HeroAggregator()

        self.hands = [
            HeroHandData(
                hand_id='h1',
                timestamp='2026-03-23T10:00:00Z',
                player_name='Hero',
                hole_cards=['Ac', 'Kc', 'Qc', 'Jc'],
                flop=['As', 'Ks', 'Qs'],
                turn='Js',
                river='Ts',
                street='RIVER',
                variant='plo4-9max',
                stack_zar=10000,
                table_id='table_1',
                seat_index=2,
            ),
            HeroHandData(
                hand_id='h2',
                timestamp='2026-03-23T10:05:00Z',
                player_name='Hero',
                hole_cards=['Ad', 'Kd', 'Qd', 'Jd'],
                flop=['2h', '3h', '4h'],
                turn=None,
                river=None,
                street='FLOP',
                variant='plo4-9max',
                stack_zar=9500,
                table_id='table_1',
                seat_index=2,
            ),
            HeroHandData(
                hand_id='h3',
                timestamp='2026-03-23T10:10:00Z',
                player_name='Hero',
                hole_cards=['Ah', 'Kh', 'Qh', 'Jh', 'Th'],
                flop=['9s', '8s', '7s'],
                turn='6s',
                river=None,
                street='TURN',
                variant='plo5-9max',
                stack_zar=12000,
                table_id='table_2',
                seat_index=5,
            ),
        ]

        self.agg.add_hands(self.hands)

    def test_basic_aggregation(self):
        """Test basic aggregation statistics"""
        stats = self.agg.compute_stats()

        self.assertEqual(stats.player_name, 'Hero')
        self.assertEqual(stats.total_hands, 3)
        self.assertEqual(stats.tables_played, 2)
        self.assertAlmostEqual(stats.average_stack_zar, 10500, places=0)
        self.assertEqual(stats.max_stack_zar, 12000)
        self.assertEqual(stats.min_stack_zar, 9500)

    def test_variant_breakdown(self):
        """Test variant aggregation"""
        stats = self.agg.compute_stats()

        self.assertEqual(stats.hands_by_variant['plo4-9max'], 2)
        self.assertEqual(stats.hands_by_variant['plo5-9max'], 1)

    def test_street_breakdown(self):
        """Test street aggregation"""
        stats = self.agg.compute_stats()

        self.assertEqual(stats.hands_by_street['RIVER'], 1)
        self.assertEqual(stats.hands_by_street['FLOP'], 1)
        self.assertEqual(stats.hands_by_street['TURN'], 1)

    def test_filter_by_variant(self):
        """Test filtering by variant"""
        plo4_agg = self.agg.filter_by_variant('plo4-9max')
        stats = plo4_agg.compute_stats()

        self.assertEqual(stats.total_hands, 2)
        self.assertEqual(len(stats.hands_by_variant), 1)
        self.assertIn('plo4-9max', stats.hands_by_variant)

    def test_filter_by_street(self):
        """Test filtering by street"""
        flop_agg = self.agg.filter_by_street('FLOP')
        stats = flop_agg.compute_stats()

        self.assertEqual(stats.total_hands, 1)
        self.assertEqual(stats.hands_by_street['FLOP'], 1)

    def test_filter_by_table(self):
        """Test filtering by table"""
        table1_agg = self.agg.filter_by_table('table_1')
        stats = table1_agg.compute_stats()

        self.assertEqual(stats.total_hands, 2)
        self.assertEqual(stats.tables_played, 1)

    def test_starting_hand_distribution(self):
        """Test starting hand frequency"""
        dist = self.agg.get_starting_hand_distribution(top_n=10)

        self.assertIsInstance(dist, list)
        self.assertTrue(len(dist) <= 10)
        # Each entry is (hole_cards, count)
        for cards, count in dist:
            self.assertIsInstance(cards, str)
            self.assertIsInstance(count, int)
            self.assertGreater(count, 0)

    def test_variant_breakdown_detailed(self):
        """Test detailed variant breakdown"""
        breakdown = self.agg.get_variant_breakdown()

        self.assertIn('plo4-9max', breakdown)
        self.assertIn('plo5-9max', breakdown)
        self.assertEqual(breakdown['plo4-9max']['hands'], 2)
        self.assertEqual(breakdown['plo5-9max']['hands'], 1)

    def test_empty_aggregator(self):
        """Test aggregator with no hands"""
        empty_agg = HeroAggregator()
        stats = empty_agg.compute_stats()

        self.assertEqual(stats.total_hands, 0)
        self.assertEqual(stats.tables_played, 0)
        self.assertEqual(len(stats.hands_by_variant), 0)

    def test_add_hand_type_validation(self):
        """Test that adding non-HeroHandData raises TypeError"""
        with self.assertRaises(TypeError):
            self.agg.add_hand({'not': 'HeroHandData'})

    def test_export_to_dict(self):
        """Test export to dictionary"""
        data = self.agg.export_to_dict()

        self.assertIn('stats', data)
        self.assertIn('hands', data)
        self.assertIn('hand_count', data)
        self.assertEqual(data['hand_count'], 3)
        self.assertEqual(len(data['hands']), 3)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and failure scenarios"""

    def test_empty_snapshot(self):
        """Test extraction from empty snapshot"""
        extractor = HeroOnlyExtractor(strict_mode=False)
        result = extractor.extract_from_snapshot({})

        self.assertIsNone(result)

    def test_missing_required_fields(self):
        """Test extraction with missing required fields"""
        extractor = HeroOnlyExtractor(strict_mode=False)

        snapshot = {
            'seats': [
                {
                    'is_hero': True,
                    # Missing hole_cards, name, etc.
                },
            ],
        }

        result = extractor.extract_from_snapshot(snapshot)
        self.assertIsNone(result)

    def test_plo6_and_plo7_variants(self):
        """Test extraction with PLO6 and PLO7 variants"""
        extractor = HeroOnlyExtractor(strict_mode=True)

        for card_count in [6, 7]:
            snapshot = {
                'table_id': f'table_{card_count}',
                'variant': f'plo{card_count}-9max',
                'seats': [
                    {
                        'seat_index': 0,
                        'name': 'Hero',
                        'hole_cards': ['As', 'Kh', 'Qd', 'Jc', 'Ts', '9h', '8d'][:card_count],
                        'is_hero': True,
                        'stack_zar': 10000,
                    },
                ],
            }

            result = extractor.extract_from_snapshot(snapshot)
            self.assertIsNotNone(result)
            self.assertEqual(len(result.hole_cards), card_count)

    def test_stats_cache_invalidation(self):
        """Test that stats cache invalidates on new hand"""
        agg = HeroAggregator()

        hand1 = HeroHandData(
            hand_id='h1',
            timestamp='2026-03-23T10:00:00Z',
            player_name='Hero',
            hole_cards=['Ac', 'Kc', 'Qc', 'Jc'],
            flop=[],
            turn=None,
            river=None,
            street='PREFLOP',
            variant='plo4-9max',
            stack_zar=10000,
            table_id='table_1',
            seat_index=2,
        )

        agg.add_hand(hand1)
        stats1 = agg.compute_stats()
        self.assertEqual(stats1.total_hands, 1)

        # Add another hand
        hand2 = HeroHandData(
            hand_id='h2',
            timestamp='2026-03-23T10:05:00Z',
            player_name='Hero',
            hole_cards=['Ad', 'Kd', 'Qd', 'Jd'],
            flop=[],
            turn=None,
            river=None,
            street='PREFLOP',
            variant='plo4-9max',
            stack_zar=10000,
            table_id='table_1',
            seat_index=2,
        )

        agg.add_hand(hand2)
        stats2 = agg.compute_stats()
        self.assertEqual(stats2.total_hands, 2)


if __name__ == '__main__':
    print("=" * 70)
    print("HERO-ONLY DATA EXTRACTION & AGGREGATION TEST SUITE")
    print("=" * 70)
    print("\nRunning tests to verify:")
    print("  ✓ Hero identification via selfPlayer/is_hero flag")
    print("  ✓ No opponent data leakage")
    print("  ✓ Rejection of invalid/mixed data")
    print("  ✓ Correct aggregation of Hero-only stats")
    print("  ✓ Proper filtering and edge case handling")
    print("\n" + "-" * 70 + "\n")

    unittest.main(verbosity=2)
