#!/usr/bin/env python3
"""
Hero-Only Data Aggregator

Aggregates statistics from Hero-only hand histories.
NO opponent data mixing - only Hero's performance across hands.

Computes:
- Hands played, by variant and street
- Stack changes and results
- Starting hand frequencies
- Street progression (preflop -> flop -> turn -> river)
- Session statistics
"""

from typing import List, Dict, Optional, Any
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import statistics

from hero_only_extractor import HeroHandData


@dataclass
class HeroSessionStats:
    """Aggregated statistics for Hero across a session/dataset"""
    player_name: str
    total_hands: int

    # By variant
    hands_by_variant: Dict[str, int]

    # By street
    hands_by_street: Dict[str, int]

    # Starting hands (hole cards frequency)
    hole_cards_frequency: Dict[str, int]  # "AcKcQcJc" -> count

    # Stack statistics
    total_stack_invested: float  # Sum of starting stacks
    average_stack_zar: float
    max_stack_zar: float
    min_stack_zar: float

    # Results (if available)
    total_won: float
    total_hands_with_result: int
    win_rate: Optional[float]  # None if no result data

    # Time range
    first_hand_time: str
    last_hand_time: str
    session_duration_minutes: float

    # Table distribution
    tables_played: int
    hands_per_table: Dict[str, int]

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


class HeroAggregator:
    """
    Aggregates Hero-only data across multiple hands.
    Prevents any opponent stat mixing.
    """

    def __init__(self):
        """Initialize aggregator"""
        self.hands: List[HeroHandData] = []
        self._stats_cache: Optional[HeroSessionStats] = None
        self._cache_dirty = True

    def add_hand(self, hand: HeroHandData):
        """
        Add a single Hero hand to the aggregation.

        Args:
            hand: HeroHandData object (must be Hero-only)
        """
        if not isinstance(hand, HeroHandData):
            raise TypeError(f"Expected HeroHandData, got {type(hand)}")

        self.hands.append(hand)
        self._cache_dirty = True

    def add_hands(self, hands: List[HeroHandData]):
        """
        Add multiple Hero hands to the aggregation.

        Args:
            hands: List of HeroHandData objects
        """
        for hand in hands:
            self.add_hand(hand)

    def clear(self):
        """Clear all hands and reset statistics"""
        self.hands.clear()
        self._stats_cache = None
        self._cache_dirty = True

    def compute_stats(self, force_recompute: bool = False) -> HeroSessionStats:
        """
        Compute aggregated statistics for Hero.

        Args:
            force_recompute: If True, recompute even if cached

        Returns:
            HeroSessionStats with aggregated data
        """
        if not self._cache_dirty and self._stats_cache and not force_recompute:
            return self._stats_cache

        if not self.hands:
            # Return empty stats
            return HeroSessionStats(
                player_name='Unknown',
                total_hands=0,
                hands_by_variant={},
                hands_by_street={},
                hole_cards_frequency={},
                total_stack_invested=0,
                average_stack_zar=0,
                max_stack_zar=0,
                min_stack_zar=0,
                total_won=0,
                total_hands_with_result=0,
                win_rate=None,
                first_hand_time='',
                last_hand_time='',
                session_duration_minutes=0,
                tables_played=0,
                hands_per_table={},
            )

        # Collect data
        player_names = set()
        variants = Counter()
        streets = Counter()
        hole_cards_counter = Counter()
        stacks = []
        tables = Counter()
        timestamps = []
        total_won = 0
        hands_with_result = 0

        for hand in self.hands:
            player_names.add(hand.player_name)
            variants[hand.variant] += 1
            streets[hand.street] += 1

            # Normalize hole cards for frequency count
            hole_str = ''.join(sorted(hand.hole_cards))
            hole_cards_counter[hole_str] += 1

            stacks.append(hand.stack_zar)
            tables[hand.table_id] += 1
            timestamps.append(hand.timestamp)

            # Results (if available)
            if hand.won_amount is not None:
                total_won += hand.won_amount
                hands_with_result += 1

        # Determine player name (should be consistent, but take most common)
        player_name = max(player_names, key=lambda n: sum(1 for h in self.hands if h.player_name == n)) if player_names else 'Unknown'

        # Time range
        sorted_timestamps = sorted(timestamps)
        first_time = sorted_timestamps[0]
        last_time = sorted_timestamps[-1]

        try:
            first_dt = datetime.fromisoformat(first_time.replace('Z', '+00:00'))
            last_dt = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
            duration_minutes = (last_dt - first_dt).total_seconds() / 60
        except:
            duration_minutes = 0

        # Win rate
        win_rate = None
        if hands_with_result > 0:
            win_rate = total_won / hands_with_result

        stats = HeroSessionStats(
            player_name=player_name,
            total_hands=len(self.hands),
            hands_by_variant=dict(variants),
            hands_by_street=dict(streets),
            hole_cards_frequency=dict(hole_cards_counter.most_common(50)),  # Top 50 starting hands
            total_stack_invested=sum(stacks),
            average_stack_zar=statistics.mean(stacks) if stacks else 0,
            max_stack_zar=max(stacks) if stacks else 0,
            min_stack_zar=min(stacks) if stacks else 0,
            total_won=total_won,
            total_hands_with_result=hands_with_result,
            win_rate=win_rate,
            first_hand_time=first_time,
            last_hand_time=last_time,
            session_duration_minutes=duration_minutes,
            tables_played=len(tables),
            hands_per_table=dict(tables),
        )

        self._stats_cache = stats
        self._cache_dirty = False
        return stats

    def filter_by_variant(self, variant: str) -> 'HeroAggregator':
        """
        Create a new aggregator with only hands matching the variant.

        Args:
            variant: Variant to filter (e.g., 'plo5-9max')

        Returns:
            New HeroAggregator with filtered hands
        """
        filtered = HeroAggregator()
        filtered.add_hands([h for h in self.hands if h.variant == variant])
        return filtered

    def filter_by_street(self, street: str) -> 'HeroAggregator':
        """
        Create a new aggregator with only hands reaching the specified street.

        Args:
            street: Street to filter (e.g., 'FLOP', 'TURN', 'RIVER')

        Returns:
            New HeroAggregator with filtered hands
        """
        filtered = HeroAggregator()
        filtered.add_hands([h for h in self.hands if h.street == street])
        return filtered

    def filter_by_date_range(self, start: str, end: str) -> 'HeroAggregator':
        """
        Create a new aggregator with only hands in the date range.

        Args:
            start: ISO format start date (inclusive)
            end: ISO format end date (inclusive)

        Returns:
            New HeroAggregator with filtered hands
        """
        try:
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        except:
            return HeroAggregator()  # Empty on parse error

        filtered = HeroAggregator()
        for hand in self.hands:
            try:
                hand_dt = datetime.fromisoformat(hand.timestamp.replace('Z', '+00:00'))
                if start_dt <= hand_dt <= end_dt:
                    filtered.add_hand(hand)
            except:
                continue

        return filtered

    def filter_by_table(self, table_id: str) -> 'HeroAggregator':
        """
        Create a new aggregator with only hands from a specific table.

        Args:
            table_id: Table ID to filter

        Returns:
            New HeroAggregator with filtered hands
        """
        filtered = HeroAggregator()
        filtered.add_hands([h for h in self.hands if h.table_id == table_id])
        return filtered

    def get_starting_hand_distribution(self, top_n: int = 20) -> List[tuple]:
        """
        Get most frequently played starting hands by Hero.

        Args:
            top_n: Number of top hands to return

        Returns:
            List of (hole_cards, count) tuples, sorted by frequency
        """
        stats = self.compute_stats()
        sorted_hands = sorted(
            stats.hole_cards_frequency.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_hands[:top_n]

    def get_variant_breakdown(self) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed breakdown by variant.

        Returns:
            Dict mapping variant -> {hands, avg_stack, ...}
        """
        breakdown = {}

        for variant in set(h.variant for h in self.hands):
            variant_agg = self.filter_by_variant(variant)
            variant_stats = variant_agg.compute_stats()

            breakdown[variant] = {
                'hands': variant_stats.total_hands,
                'avg_stack': variant_stats.average_stack_zar,
                'total_won': variant_stats.total_won,
                'win_rate': variant_stats.win_rate,
            }

        return breakdown

    def get_street_progression(self) -> Dict[str, int]:
        """
        Get hand counts by street (shows how many hands reached each street).

        Returns:
            Dict mapping street -> hand count
        """
        stats = self.compute_stats()
        return stats.hands_by_street

    def export_to_dict(self) -> Dict:
        """
        Export all Hero hands and stats to a dictionary.

        Returns:
            Dict with 'hands' and 'stats' keys
        """
        return {
            'stats': self.compute_stats().to_dict(),
            'hands': [h.to_dict() for h in self.hands],
            'hand_count': len(self.hands),
        }

    def export_to_json_file(self, output_path: str):
        """
        Export aggregated data to JSON file.

        Args:
            output_path: Path to output JSON file
        """
        import json
        from pathlib import Path

        data = self.export_to_dict()
        Path(output_path).write_text(json.dumps(data, indent=2), encoding='utf-8')


def aggregate_from_directory(directory: str, variant: Optional[str] = None) -> HeroAggregator:
    """
    Load and aggregate all validated hands from a directory.

    Args:
        directory: Path to directory containing validated hand JSON files
        variant: Optional variant filter

    Returns:
        HeroAggregator with all loaded hands
    """
    from pathlib import Path
    from hero_only_extractor import HeroOnlyExtractor

    extractor = HeroOnlyExtractor(strict_mode=False)
    aggregator = HeroAggregator()

    directory_path = Path(directory)
    if not directory_path.exists():
        return aggregator

    for json_file in directory_path.glob('*.json'):
        hero_data = extractor.extract_from_validated_hand(json_file)
        if hero_data:
            if variant is None or hero_data.variant == variant:
                aggregator.add_hand(hero_data)

    return aggregator


if __name__ == '__main__':
    # Example usage
    from hero_only_extractor import HeroHandData

    # Create sample Hero hands
    hands = [
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

    # Aggregate
    agg = HeroAggregator()
    agg.add_hands(hands)

    # Compute stats
    stats = agg.compute_stats()
    print(f"✓ Hero Stats: {stats.player_name}")
    print(f"  Total hands: {stats.total_hands}")
    print(f"  Variants: {stats.hands_by_variant}")
    print(f"  Streets: {stats.hands_by_street}")
    print(f"  Avg stack: {stats.average_stack_zar:.2f} ZAR")
    print(f"  Tables played: {stats.tables_played}")
    print(f"  Session duration: {stats.session_duration_minutes:.1f} minutes")

    # Filter by variant
    plo5_agg = agg.filter_by_variant('plo5-9max')
    plo5_stats = plo5_agg.compute_stats()
    print(f"\n✓ PLO5 Only: {plo5_stats.total_hands} hands")

    # Get breakdown
    breakdown = agg.get_variant_breakdown()
    print(f"\n✓ Variant Breakdown:")
    for variant, data in breakdown.items():
        print(f"  {variant}: {data['hands']} hands, avg stack {data['avg_stack']:.2f}")
