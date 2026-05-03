// variantRules.js
// Single source of truth for variant structure.
//
// All application components MUST call parseVariant(activeVariant) before
// performing any operation on hand data: validation, parsing, rendering,
// RNG preparation, or storage.
//
// No module may bypass this step.
//
// Supported variant keys (lowercase, as used in UI selects):
//   plo4-6max  plo4-8max  plo4-9max
//   plo5-5max  plo5-6max  plo5-8max  plo5-9max
//   plo6-5max  plo6-6max  plo6-8max
//   plo7-5max  plo7-6max
//
// Returned rules object shape:
// {
//   variant:          string   -- canonical uppercase label, e.g. "PLO5-6MAX"
//   plo_n:            number   -- hole cards per player (4 | 5 | 6 | 7)
//   players:          number   -- seats at the table
//   hole_cards:       number   -- alias for plo_n
//   flop_cards:       number   -- always 3
//   total_lines_min:  number   -- minimum non-empty input lines (pre-flop only)
//   total_lines_max:  number   -- maximum non-empty input lines (flop + turn)
//   total_lines_flop: number   -- exact non-empty lines when flop is present
//   flop_line:        number   -- 1-based index of flop line (= players + 1)
//   total_cards:      number   -- all hole cards + flop (= players*hole_cards + 3)
//   total_characters: number   -- total_cards * 2 (each card = 2 chars)
//   chars_per_hand:   number   -- hole_cards * 2
//   chars_per_flop:   number   -- flop_cards * 2  (always 6)
// }

const FLOP_CARDS = 3

/**
 * parse_variant
 *
 * Derives all structural rules from the active variant key.
 * Must be called before any validation, parsing, rendering, RNG, or storage.
 *
 * @param {string} variantKey  e.g. "plo5-6max" or "PLO5-6MAX"
 * @returns {object}           rules — see shape above
 * @throws {Error}             if variant key is not recognised
 */
export function parseVariant(variantKey) {
  if (!variantKey) throw new Error('parseVariant: variantKey is required')

  // Normalise: lowercase, strip whitespace
  const key = String(variantKey).toLowerCase().trim()

  // Parse: plo{N}-{P}max  e.g. "plo5-6max" → ploN=5, players=6
  const match = key.match(/^plo(\d+)-(\d+)max$/)
  if (!match) {
    throw new Error(
      `parseVariant: unrecognised variant "${variantKey}". ` +
      `Expected format plo{N}-{P}max (e.g. plo5-6max).`
    )
  }

  const ploN    = parseInt(match[1], 10)   // hole cards per player
  const players = parseInt(match[2], 10)   // seats

  // Validate supported values
  if (![4, 5, 6, 7].includes(ploN)) {
    throw new Error(
      `parseVariant: unsupported PLO variant ${ploN} in "${variantKey}". ` +
      `Supported: PLO4, PLO5, PLO6, PLO7.`
    )
  }
  if (players < 2 || players > 9) {
    throw new Error(
      `parseVariant: unsupported player count ${players} in "${variantKey}". ` +
      `Supported: 2–9.`
    )
  }

  const variant         = `PLO${ploN}-${players}MAX`
  const hole_cards      = ploN
  const flop_cards      = FLOP_CARDS
  const flop_line       = players + 1         // 1-based
  const total_lines_min = players             // pre-flop: exactly N player lines
  const total_lines_flop = players + 1        // flop present: N player lines + 1 flop line
  const total_lines_max = players + 2         // flop + turn: N + 2

  const total_cards      = players * hole_cards + flop_cards
  const total_characters = total_cards * 2
  const chars_per_hand   = hole_cards * 2
  const chars_per_flop   = flop_cards * 2     // always 6

  return {
    variant,
    plo_n:            ploN,
    players,
    hole_cards,
    flop_cards,
    total_lines_min,
    total_lines_flop,
    total_lines_max,
    flop_line,
    total_cards,
    total_characters,
    chars_per_hand,
    chars_per_flop,
  }
}

/**
 * variantErrorMessage
 *
 * Returns a variant-aware error string for line-count mismatches.
 * Used wherever input line counts are validated.
 *
 * @param {object} rules   result of parseVariant()
 * @param {number} got     actual non-empty line count
 * @returns {string}
 */
export function variantErrorMessage(rules, got) {
  const { variant, players, total_lines_min, total_lines_max } = rules
  return (
    `Variant ${variant} requires ${total_lines_min}–${total_lines_max} non-empty lines ` +
    `(${players} player hands + optional flop/turn), got ${got}`
  )
}

/**
 * variantLabel
 *
 * Human-readable summary of a variant's key parameters.
 * Suitable for UI display and log output.
 *
 * @param {object} rules   result of parseVariant()
 * @returns {string}       e.g. "PLO5-6MAX · 6 players · 5 hole cards · 33 cards · 66 chars"
 */
export function variantLabel(rules) {
  const { variant, players, hole_cards, total_cards, total_characters } = rules
  return (
    `${variant} · ${players} players · ${hole_cards} hole cards · ` +
    `${total_cards} cards · ${total_characters} chars`
  )
}
