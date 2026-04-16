#!/usr/bin/env python3
"""
Hero-Only Data Extractor

Strictly extracts and validates Hero (selfPlayer) data from hand histories.
ZERO opponent leakage - only processes players explicitly marked as selfPlayer/is_hero.

Rules:
1. Identify Hero via selfPlayer/is_hero flag or face-up cards (readable class)
2. Ignore ALL other players unless explicitly marked as selfPlayer
3. Do NOT include opponents with face-down cards or unknown hole cards
4. Do NOT infer or guess opponent cards under any circumstance
5. Extract only Hero's data per hand (cards, actions, results)
6. Aggregate only Hero's entries across hands (no opponent stats mixing)

Failure modes prevented:
- Including players with hidden/facedown cards
- Mixing opponent stats into Hero aggregates
- Treating all players equally instead of filtering for selfPlayer
"""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class HeroHandData:
    """Single hand data for Hero only - no opponent information"""
    hand_id: str
    timestamp: str
    player_name: str
    hole_cards: List[str]  # Hero's cards only
    flop: List[str]
    turn: Optional[str]
    river: Optional[str]
    street: str
    variant: str
    stack_zar: float
    table_id: str
    seat_index: int

    # Hero's actions and results (future expansion)
    actions: List[Dict[str, Any]] = None
    final_pot: Optional[float] = None
    won_amount: Optional[float] = None

    def __post_init__(self):
        """Validate Hero data on construction"""
        if self.actions is None:
            self.actions = []

        # Validate hole cards exist and are valid
        if not self.hole_cards or len(self.hole_cards) < 4:
            raise ValueError(f"Hero must have 4+ hole cards, got {len(self.hole_cards)}")

        # Validate no duplicate cards
        all_cards = self.hole_cards + self.flop
        if self.turn:
            all_cards.append(self.turn)
        if self.river:
            all_cards.append(self.river)

        if len(all_cards) != len(set(all_cards)):
            raise ValueError(f"Duplicate cards detected: {all_cards}")

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


class HeroOnlyExtractor:
    """
    Extracts ONLY Hero data from various hand history formats.
    Prevents any opponent data leakage.
    """

    def __init__(self, strict_mode: bool = True):
        """
        Args:
            strict_mode: If True, raises exceptions on any validation failure.
                        If False, logs warnings and continues.
        """
        self.strict_mode = strict_mode
        self.extraction_count = 0
        self.rejection_count = 0
        self.rejection_reasons = []

    def extract_from_snapshot(self, snapshot: Dict) -> Optional[HeroHandData]:
        """
        Extract Hero data from a snapshot payload (POST /api/snapshot format).

        Args:
            snapshot: Snapshot dict with 'seats' list and table metadata

        Returns:
            HeroHandData if Hero found and valid, None otherwise

        Raises:
            ValueError: If strict_mode=True and validation fails
        """
        # Find Hero seat - must have is_hero=True flag
        hero_seat = None
        for seat in snapshot.get('seats', []):
            if seat.get('is_hero') is True:
                hero_seat = seat
                break

        if not hero_seat:
            msg = "No seat with is_hero=True found in snapshot"
            if self.strict_mode:
                raise ValueError(msg)
            self.rejection_reasons.append(msg)
            self.rejection_count += 1
            return None

        # Validate Hero has hole cards (face-up)
        hole_cards = hero_seat.get('hole_cards', [])
        if not hole_cards or len(hole_cards) < 4:
            msg = f"Hero seat has insufficient hole cards: {len(hole_cards)}"
            if self.strict_mode:
                raise ValueError(msg)
            self.rejection_reasons.append(msg)
            self.rejection_count += 1
            return None

        # Extract board cards
        board = snapshot.get('board', {})
        flop = board.get('flop', [])
        turn = board.get('turn')
        river = board.get('river')

        # Build HeroHandData
        try:
            hero_data = HeroHandData(
                hand_id=snapshot.get('hand_id', f"snap_{snapshot.get('table_id')}_{hero_seat.get('seat_index')}"),
                timestamp=snapshot.get('timestamp_utc') or datetime.now(timezone.utc).isoformat(),
                player_name=hero_seat.get('name', 'Unknown'),
                hole_cards=hole_cards,
                flop=flop if isinstance(flop, list) else [],
                turn=turn if turn else None,
                river=river if river else None,
                street=snapshot.get('street', 'PREFLOP'),
                variant=snapshot.get('variant', 'plo'),
                stack_zar=hero_seat.get('stack_zar', 0),
                table_id=snapshot.get('table_id', 'unknown'),
                seat_index=hero_seat.get('seat_index', -1),
            )
            self.extraction_count += 1
            return hero_data
        except ValueError as e:
            if self.strict_mode:
                raise
            self.rejection_reasons.append(str(e))
            self.rejection_count += 1
            return None

    def extract_from_tracker_payload(self, payload: Dict) -> Optional[HeroHandData]:
        """
        Extract Hero data from tracker API payload (from Tampermonkey script).

        This format already contains ONLY Hero data - the script only sends Hero's cards.

        Args:
            payload: Tracker payload dict with hole_cards, flop, player_name, etc.

        Returns:
            HeroHandData if valid, None otherwise
        """
        # Tracker payload is already Hero-only by design
        hole_cards = payload.get('hole_cards', [])
        if not hole_cards or len(hole_cards) < 4:
            msg = f"Tracker payload has insufficient hole cards: {len(hole_cards)}"
            if self.strict_mode:
                raise ValueError(msg)
            self.rejection_reasons.append(msg)
            self.rejection_count += 1
            return None

        try:
            hero_data = HeroHandData(
                hand_id=payload.get('hand_id', payload.get('payload_id', f"trk_{datetime.now(timezone.utc).timestamp()}")),
                timestamp=payload.get('timestamp_utc') or datetime.now(timezone.utc).isoformat(),
                player_name=payload.get('player_name', 'Unknown'),
                hole_cards=hole_cards,
                flop=payload.get('flop', []),
                turn=payload.get('turn'),
                river=payload.get('river'),
                street=payload.get('street', 'PREFLOP'),
                variant=payload.get('variant', 'plo'),
                stack_zar=payload.get('stack_zar', 0),
                table_id=payload.get('table_id', payload.get('source_key', 'unknown')),
                seat_index=-1,  # Not available in tracker format
            )
            self.extraction_count += 1
            return hero_data
        except ValueError as e:
            if self.strict_mode:
                raise
            self.rejection_reasons.append(str(e))
            self.rejection_count += 1
            return None

    def extract_from_validated_hand(self, validated_path: Path) -> Optional[HeroHandData]:
        """
        Extract Hero data from validated hand JSON file.

        Args:
            validated_path: Path to validated hand JSON file

        Returns:
            HeroHandData if valid, None otherwise
        """
        try:
            content = validated_path.read_text(encoding='utf-8')
            data = json.loads(content)

            # Validated hands are already Hero-only from tracker
            return self.extract_from_tracker_payload(data)
        except (json.JSONDecodeError, FileNotFoundError, ValueError) as e:
            msg = f"Failed to parse validated hand {validated_path}: {e}"
            if self.strict_mode:
                raise ValueError(msg)
            self.rejection_reasons.append(msg)
            self.rejection_count += 1
            return None

    def validate_no_opponent_data(self, data: Any) -> bool:
        """
        Validate that the data structure contains NO opponent information.

        This is a defensive check to prevent accidental opponent leakage.

        Args:
            data: Data structure to validate (dict, HeroHandData, etc.)

        Returns:
            True if valid (no opponent data), False otherwise
        """
        if isinstance(data, HeroHandData):
            # HeroHandData is designed to only hold Hero info
            return True

        if isinstance(data, dict):
            # Check for common opponent data fields
            opponent_indicators = [
                'opponents', 'villain', 'other_players', 'all_players',
                'villain_cards', 'opponent_cards', 'other_hole_cards'
            ]

            for key in data.keys():
                if any(indicator in key.lower() for indicator in opponent_indicators):
                    self.rejection_reasons.append(f"Found opponent data indicator: {key}")
                    return False

            # Check for seats array with multiple players having hole_cards
            if 'seats' in data:
                hero_count = 0
                other_cards_count = 0

                for seat in data['seats']:
                    if seat.get('is_hero'):
                        hero_count += 1
                    elif seat.get('hole_cards'):
                        # Non-hero seat has hole cards - this is opponent data!
                        other_cards_count += 1

                if hero_count != 1:
                    self.rejection_reasons.append(f"Expected exactly 1 Hero, found {hero_count}")
                    return False

                if other_cards_count > 0:
                    self.rejection_reasons.append(f"Found {other_cards_count} opponents with hole cards")
                    return False

        return True

    def get_stats(self) -> Dict:
        """Get extraction statistics"""
        return {
            'extraction_count': self.extraction_count,
            'rejection_count': self.rejection_count,
            'success_rate': self.extraction_count / (self.extraction_count + self.rejection_count) if (self.extraction_count + self.rejection_count) > 0 else 0,
            'recent_rejections': self.rejection_reasons[-10:],  # Last 10 rejection reasons
        }


def extract_hero_batch(sources: List[Any], extractor: HeroOnlyExtractor = None) -> List[HeroHandData]:
    """
    Extract Hero data from multiple sources.

    Args:
        sources: List of dicts, Paths, or other supported formats
        extractor: Optional extractor instance (creates new one if None)

    Returns:
        List of HeroHandData objects (only valid Hero hands)
    """
    if extractor is None:
        extractor = HeroOnlyExtractor(strict_mode=False)

    results = []

    for source in sources:
        try:
            if isinstance(source, Path):
                hero_data = extractor.extract_from_validated_hand(source)
            elif isinstance(source, dict):
                # Try snapshot format first, then tracker format
                if 'seats' in source:
                    hero_data = extractor.extract_from_snapshot(source)
                else:
                    hero_data = extractor.extract_from_tracker_payload(source)
            else:
                continue

            if hero_data:
                results.append(hero_data)
        except Exception as e:
            # Log but continue processing
            print(f"Extraction error: {e}")
            continue

    return results


if __name__ == '__main__':
    # Example usage and validation
    extractor = HeroOnlyExtractor(strict_mode=True)

    # Test case 1: Valid snapshot with Hero
    test_snapshot = {
        'table_id': 'test_table_1',
        'hand_id': 'hand_001',
        'timestamp_utc': '2026-03-23T12:00:00Z',
        'street': 'FLOP',
        'variant': 'plo5-9max',
        'board': {
            'flop': ['As', 'Kh', 'Qd'],
            'turn': None,
            'river': None,
        },
        'seats': [
            {
                'seat_index': 0,
                'name': 'Hero123',
                'stack_zar': 10000,
                'hole_cards': ['Ac', 'Kc', 'Qc', 'Jc', 'Tc'],
                'is_hero': True,
                'status': 'playing',
            },
            {
                'seat_index': 1,
                'name': 'Opponent1',
                'stack_zar': 8000,
                'hole_cards': [],  # Face down - no data
                'is_hero': False,
                'status': 'playing',
            },
        ],
    }

    hero_data = extractor.extract_from_snapshot(test_snapshot)
    print(f"✓ Extracted Hero data: {hero_data.player_name} with {len(hero_data.hole_cards)} cards")
    print(f"  Validation: {extractor.validate_no_opponent_data(hero_data)}")

    # Test case 2: Invalid - no Hero flag
    invalid_snapshot = {
        'table_id': 'test_table_2',
        'seats': [
            {
                'seat_index': 0,
                'name': 'Player1',
                'hole_cards': ['As', 'Kh', 'Qd', 'Jc'],
                'is_hero': False,  # Not Hero!
            },
        ],
    }

    extractor_lenient = HeroOnlyExtractor(strict_mode=False)
    result = extractor_lenient.extract_from_snapshot(invalid_snapshot)
    print(f"✓ Invalid snapshot rejected: {result is None}")
    print(f"  Stats: {extractor_lenient.get_stats()}")
