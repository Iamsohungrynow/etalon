/**
 * Physical quantities as the user types and reads them (ui-ux-spec §6, plan-u1 §5).
 *
 * API units are µm for length, s for time and Hz for frequency (CLAUDE.md "Units").
 * Every conversion is a power of ten, applied to the decimal text of the number rather
 * than by floating-point multiplication, so "1550 nm" becomes exactly the double 1.55
 * and 1.55 µm shown in nm is exactly 1550 (not 1550.0000000000002).
 */

export type Quantity = "length" | "time" | "frequency";
export type Unit = "um" | "nm" | "m" | "s" | "ps" | "fs" | "Hz" | "GHz" | "THz";

interface UnitInfo {
  quantity: Quantity;
  /** value in API units = value in this unit × 10^exponent */
  exponent: number;
  symbol: string;
}

const UNITS: Record<Unit, UnitInfo> = {
  um: { quantity: "length", exponent: 0, symbol: "µm" },
  nm: { quantity: "length", exponent: -3, symbol: "nm" },
  m: { quantity: "length", exponent: 6, symbol: "m" },
  s: { quantity: "time", exponent: 0, symbol: "s" },
  ps: { quantity: "time", exponent: -12, symbol: "ps" },
  fs: { quantity: "time", exponent: -15, symbol: "fs" },
  Hz: { quantity: "frequency", exponent: 0, symbol: "Hz" },
  GHz: { quantity: "frequency", exponent: 9, symbol: "GHz" },
  THz: { quantity: "frequency", exponent: 12, symbol: "THz" },
};

/** What a user may type after the number. "u" stands for µ; both the micro sign (U+00B5)
 *  and the Greek mu (U+03BC) are accepted. Frequency units also in lower case. */
const ALIASES: Record<string, Unit> = {
  um: "um",
  "µm": "um",
  "μm": "um",
  nm: "nm",
  m: "m",
  s: "s",
  ps: "ps",
  fs: "fs",
  Hz: "Hz",
  hz: "Hz",
  GHz: "GHz",
  ghz: "GHz",
  THz: "THz",
  thz: "THz",
};

/** The unit the API speaks for each quantity. */
export const API_UNIT: Record<Quantity, Unit> = { length: "um", time: "s", frequency: "Hz" };

/** "um" → "µm"; every other unit is its own symbol. */
export function unitSymbol(unit: Unit): string {
  return UNITS[unit].symbol;
}

export function unitQuantity(unit: Unit): Quantity {
  return UNITS[unit].quantity;
}

/** value × 10^exponent, done on the shortest decimal text of the value (exact in decimal). */
function shiftDecimal(value: number, exponent: number): number {
  if (exponent === 0 || value === 0 || !Number.isFinite(value)) return value;
  const [mantissa, exp = "0"] = String(value).split("e");
  return Number(`${mantissa}e${Number(exp) + exponent}`);
}

/** A value in `unit` → API units: toApiUnits(1550, "nm") === 1.55. */
export function toApiUnits(value: number, unit: Unit): number {
  return shiftDecimal(value, UNITS[unit].exponent);
}

/** A value in API units → `unit`: fromApiUnits(1.55, "nm") === 1550. */
export function fromApiUnits(value: number, unit: Unit): number {
  return shiftDecimal(value, -UNITS[unit].exponent);
}

/** Digits after the decimal point in the shortest text of x: 1.55 → 2, 1.5e-7 → 8. */
function decimalPlaces(x: number): number {
  const [mantissa = "", exp = "0"] = String(Math.abs(x)).split("e");
  const fraction = mantissa.split(".")[1] ?? "";
  return Math.max(0, fraction.length - Number(exp));
}

/**
 * a + b without binary noise from the decimal operands: addDecimal(1.55, 0.01) === 1.56,
 * where 1.55 + 0.01 is 1.5600000000000001. Used by the arrow-key steps of NumberField.
 */
export function addDecimal(a: number, b: number): number {
  const sum = a + b;
  if (!Number.isFinite(sum)) return sum;
  const places = Math.min(100, Math.max(decimalPlaces(a), decimalPlaces(b)));
  return Number(sum.toFixed(places));
}

/** x × 10^exponent without binary noise: scaleDecimal(0.07, 1) === 0.7. */
export function scaleDecimal(x: number, exponent: number): number {
  return shiftDecimal(x, exponent);
}

/** A display unit of another quantity is a bug in the calling screen, not a user error. */
function assertUnitOf(unit: Unit, quantity: Quantity): void {
  if (UNITS[unit].quantity !== quantity) {
    throw new Error(`${unit} is not a unit of ${quantity}`);
  }
}

// sign, digits ("1", "1.", "1.55", ".5"), optional exponent, then whatever follows (the unit)
const NUMBER = /^([+-]?)(\d+(?:\.\d*)?|\.\d+)(?:[eE]([+-]?\d+))?\s*(.*)$/s;

// "1,234" or "12,500": a comma that may be a thousands separator, which we refuse to guess.
const THOUSANDS = /^[+-]?[1-9]\d{0,2},\d{3}(?!\d)/;

/**
 * Text → the value in API units, or null when it is not a number of this quantity.
 *
 * Accepts "1.55", "1.55 µm", "1.55um", "1550nm", "1.55e-6 m", "-2", ".5", a comma decimal
 * ("1,55") and a Unicode minus. A bare number is in `defaultUnit`. Returns null for "",
 * words, unknown units ("1.55 kg"), a unit of another quantity, a non-finite result and an
 * ambiguous comma ("1,550" may mean 1550). Throws if `defaultUnit` is not of `quantity`.
 */
export function parseQuantity(text: string, quantity: Quantity, defaultUnit: Unit): number | null {
  assertUnitOf(defaultUnit, quantity);
  let normalized = text.trim().replace(/−/g, "-");
  if (normalized.includes(",")) {
    const commas = normalized.split(",").length - 1;
    if (commas > 1 || normalized.includes(".") || THOUSANDS.test(normalized)) return null;
    normalized = normalized.replace(",", ".");
  }
  const match = NUMBER.exec(normalized);
  if (!match) return null;
  const [, sign = "", digits = "", exponent = "0", suffix = ""] = match;
  let unit: Unit = defaultUnit;
  if (suffix !== "") {
    const named = ALIASES[suffix.trim()];
    if (named === undefined) return null;
    unit = named;
  }
  if (UNITS[unit].quantity !== quantity) return null;
  const value = Number(`${sign}${digits}e${Number(exponent) + UNITS[unit].exponent}`);
  return Number.isFinite(value) ? value : null;
}

/**
 * A value in API units, printed in `unit` with up to `digits` significant figures and no
 * trailing zeros: 1.55 → "1.55 µm", "1550 nm"; 3e-13 s → "300 fs". No digit grouping
 * ("1550", not "1,550"); below 0.001 or from 10^6 on, scientific ("1.5e-7 µm").
 */
export function formatQuantity(
  value: number,
  quantity: Quantity,
  unit: Unit,
  locale = "en",
  digits = 4,
): string {
  assertUnitOf(unit, quantity);
  const shown = fromApiUnits(value, unit);
  const magnitude = Math.abs(shown);
  const scientific = magnitude !== 0 && Number.isFinite(magnitude) && (magnitude < 1e-3 || magnitude >= 1e6);
  const number = new Intl.NumberFormat(locale, {
    maximumSignificantDigits: digits,
    useGrouping: false,
    notation: scientific ? "scientific" : "standard",
  })
    .format(shown === 0 ? 0 : shown)
    .replace("E", "e");
  return `${number} ${unitSymbol(unit)}`;
}

/** The value in `unit` at full precision (shortest round-trip text), for editing: "1.5500001". */
export function formatFullPrecision(value: number, unit: Unit): string {
  const shown = fromApiUnits(value, unit);
  return String(shown === 0 ? 0 : shown);
}
