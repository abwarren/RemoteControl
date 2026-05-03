// CardChip.jsx — renders a single card as a coloured chip
// hand: string like "AhKhQdJd" or "Ts9s8c7c"
// Returns an array of chip spans

const SUIT_META = {
  c: { cls: 'chip-c', sym: '♣' },
  d: { cls: 'chip-d', sym: '♦' },
  h: { cls: 'chip-h', sym: '♥' },
  s: { cls: 'chip-s', sym: '♠' },
}

/**
 * Parse a hand string like "AhKhQdJd" into card tokens [{rank, suit}]
 */
export function parseHand(hand = '') {
  if (!hand) return []
  const tokens = []
  let i = 0
  const h = hand.toUpperCase()
  while (i < h.length) {
    if (h[i] === '1' && h[i + 1] === '0') {
      tokens.push({ rank: '10', suit: (h[i + 2] || '').toLowerCase() })
      i += 3
    } else {
      tokens.push({ rank: h[i], suit: (h[i + 1] || '').toLowerCase() })
      i += 2
    }
  }
  return tokens
}

export function CardChip({ rank, suit }) {
  const meta = SUIT_META[suit] || { cls: 'chip-s', sym: suit }
  return (
    <span className={`chip ${meta.cls}`}>
      {rank}{meta.sym}
    </span>
  )
}

export function HandChips({ hand, name }) {
  const cards = parseHand(hand)
  return (
    <span className="hand-row">
      {cards.map((c, i) => (
        <CardChip key={i} rank={c.rank} suit={c.suit} />
      ))}
      {name && <span className="player-name">({name})</span>}
    </span>
  )
}

export default HandChips
