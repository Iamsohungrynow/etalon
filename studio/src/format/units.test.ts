// NumberField's arithmetic: parsing what a user types, printing values with units.
import { describe, expect, it } from "vitest";
import {
  addDecimal,
  formatFullPrecision,
  formatQuantity,
  fromApiUnits,
  parseQuantity,
  scaleDecimal,
  toApiUnits,
  unitQuantity,
  unitSymbol,
} from "./units";

describe("parseQuantity: lengths in µm", () => {
  it.each([
    ["1.55", 1.55],
    ["1.55 µm", 1.55],
    ["1.55um", 1.55],
    ["1.55 um", 1.55],
    ["1.55μm", 1.55], // Greek mu, not the micro sign
    ["1550nm", 1.55],
    ["1550 nm", 1.55],
    ["1.55e-6 m", 1.55],
    ["1.55E-6m", 1.55],
    ["0.5 µm", 0.5],
    ["-2", -2],
    ["−2 µm", -2], // Unicode minus
    ["+3", 3],
    [".5", 0.5],
    ["5.", 5],
    ["1,55", 1.55],
    ["1,55 µm", 1.55],
    ["0,550", 0.55],
    ["1234,5 nm", 1.2345],
    ["  1.55  µm  ", 1.55],
    ["1.55 µm", 1.55], // no-break space
    ["0", 0],
    ["2e3 nm", 2],
    ["220 nm", 0.22],
  ])("%j → %s", (text, expected) => {
    expect(parseQuantity(text, "length", "um")).toBe(expected);
  });

  it("is exact in decimal, not in binary", () => {
    // 1550 × 0.001 would be 1.5500000000000000444…; the result is the double nearest 1.55.
    expect(parseQuantity("1550nm", "length", "um")).toBe(1.55);
    expect(parseQuantity("1.55e-6 m", "length", "um")).toBe(1.55);
    expect(parseQuantity("0.3 nm", "length", "um")).toBe(0.0003);
    expect(parseQuantity("1.1e-6 m", "length", "um")).toBe(1.1);
  });

  it("reads a bare number in the default unit", () => {
    expect(parseQuantity("1550", "length", "nm")).toBe(1.55);
    expect(parseQuantity("1.55", "length", "nm")).toBe(0.00155);
    expect(parseQuantity("1.55e-6", "length", "m")).toBe(1.55);
    expect(parseQuantity("1.55 µm", "length", "nm")).toBe(1.55); // a typed unit wins
  });

  it.each([
    "",
    "   ",
    "abc",
    "1.55 kg",
    "1.55 mm", // not a Studio unit
    "1.55 UM",
    "µm",
    "1.55 µ m",
    "1 550 nm",
    "1.5.5",
    "1e",
    "e5",
    "-",
    ".",
    "1.55 s", // a time, not a length
    "193 THz", // a frequency, not a length
    "1e999", // overflows to Infinity
    "Infinity",
    "NaN",
    "1,550", // a thousands separator or a decimal comma: refuse to guess
    "12,500 nm",
    "1,234,567",
    "1,5.5",
    "0x10",
  ])("%j → null", (text) => {
    expect(parseQuantity(text, "length", "um")).toBeNull();
  });
});

describe("parseQuantity: time in s and frequency in Hz", () => {
  it("converts time units", () => {
    expect(parseQuantity("300 fs", "time", "s")).toBe(3e-13);
    expect(parseQuantity("300fs", "time", "fs")).toBe(3e-13);
    expect(parseQuantity("300", "time", "fs")).toBe(3e-13);
    expect(parseQuantity("1.5 ps", "time", "s")).toBe(1.5e-12);
    expect(parseQuantity("2e-12 s", "time", "fs")).toBe(2e-12);
    expect(parseQuantity("1 nm", "time", "s")).toBeNull();
    expect(parseQuantity("1 Hz", "time", "s")).toBeNull();
  });

  it("converts frequency units, in either case", () => {
    expect(parseQuantity("193.4 THz", "frequency", "Hz")).toBe(1.934e14);
    expect(parseQuantity("193.4thz", "frequency", "Hz")).toBe(1.934e14);
    expect(parseQuantity("10 GHz", "frequency", "THz")).toBe(1e10);
    expect(parseQuantity("10 ghz", "frequency", "THz")).toBe(1e10);
    expect(parseQuantity("5e9 Hz", "frequency", "THz")).toBe(5e9);
    expect(parseQuantity("5e9 hz", "frequency", "THz")).toBe(5e9);
    expect(parseQuantity("193.4", "frequency", "THz")).toBe(1.934e14);
    expect(parseQuantity("1 s", "frequency", "Hz")).toBeNull();
  });

  it("throws when the default unit is not of the quantity (a bug in the caller)", () => {
    expect(() => parseQuantity("1", "length", "fs")).toThrow("fs is not a unit of length");
  });
});

describe("formatQuantity", () => {
  it("prints the brief's examples", () => {
    expect(formatQuantity(1.55, "length", "um")).toBe("1.55 µm");
    expect(formatQuantity(1.55, "length", "nm")).toBe("1550 nm");
    expect(formatQuantity(3e-13, "time", "fs")).toBe("300 fs");
  });

  it("keeps 4 significant figures by default, without trailing zeros", () => {
    expect(formatQuantity(1.5500001, "length", "um")).toBe("1.55 µm");
    expect(formatQuantity(0.22, "length", "um")).toBe("0.22 µm");
    expect(formatQuantity(10, "length", "um")).toBe("10 µm");
    expect(formatQuantity(1.23456, "length", "um")).toBe("1.235 µm");
    expect(formatQuantity(0.123456, "length", "um")).toBe("0.1235 µm");
    expect(formatQuantity(-2, "length", "um")).toBe("-2 µm");
    expect(formatQuantity(0, "length", "um")).toBe("0 µm");
    expect(formatQuantity(-0, "length", "um")).toBe("0 µm");
  });

  it("honours digits and does not group thousands", () => {
    expect(formatQuantity(1.23456, "length", "um", "en", 2)).toBe("1.2 µm");
    expect(formatQuantity(1.23456, "length", "um", "en", 6)).toBe("1.23456 µm");
    expect(formatQuantity(12.3456, "length", "nm")).toBe("12350 nm");
    expect(formatQuantity(123.456, "length", "um", "zh-CN")).toBe("123.5 µm");
    expect(formatQuantity(26.4, "length", "nm", "zh-CN")).toBe("26400 nm");
  });

  it("goes scientific below 0.001 and from 10^6", () => {
    expect(formatQuantity(1.5e-7, "length", "um")).toBe("1.5e-7 µm");
    expect(formatQuantity(1e-6, "time", "s")).toBe("1e-6 s");
    expect(formatQuantity(0.001, "length", "um")).toBe("0.001 µm");
    expect(formatQuantity(999_999, "length", "um", "en", 6)).toBe("999999 µm");
    expect(formatQuantity(1.934e14, "frequency", "Hz")).toBe("1.934e14 Hz");
  });

  it("converts frequency and time", () => {
    expect(formatQuantity(1.934e14, "frequency", "THz")).toBe("193.4 THz");
    expect(formatQuantity(1e10, "frequency", "GHz")).toBe("10 GHz");
    expect(formatQuantity(1.5e-12, "time", "ps")).toBe("1.5 ps");
    expect(formatQuantity(2, "length", "m")).toBe("2e-6 m");
  });

  it("throws on a unit of another quantity (a bug in the caller)", () => {
    expect(() => formatQuantity(1, "time", "um")).toThrow("um is not a unit of time");
  });
});

describe("unit helpers", () => {
  it("names units by their symbols", () => {
    expect(unitSymbol("um")).toBe("µm");
    expect(unitSymbol("um")).toBe("µm"); // the micro sign, as the lint allow-list has it
    expect(unitSymbol("nm")).toBe("nm");
    expect(unitSymbol("m")).toBe("m");
    expect(unitSymbol("s")).toBe("s");
    expect(unitSymbol("ps")).toBe("ps");
    expect(unitSymbol("fs")).toBe("fs");
    expect(unitSymbol("Hz")).toBe("Hz");
    expect(unitSymbol("GHz")).toBe("GHz");
    expect(unitSymbol("THz")).toBe("THz");
    expect(unitQuantity("THz")).toBe("frequency");
    expect(unitQuantity("nm")).toBe("length");
  });

  it("converts to and from API units exactly in decimal", () => {
    expect(fromApiUnits(1.55, "nm")).toBe(1550);
    expect(toApiUnits(1550, "nm")).toBe(1.55);
    expect(fromApiUnits(3e-13, "fs")).toBe(300);
    expect(toApiUnits(193.4, "THz")).toBe(1.934e14);
    expect(fromApiUnits(1.55, "m")).toBe(1.55e-6);
    expect(fromApiUnits(-0.22, "nm")).toBe(-220);
    expect(fromApiUnits(0, "nm")).toBe(0);
  });

  it("prints full precision for editing", () => {
    expect(formatFullPrecision(1.5500001, "um")).toBe("1.5500001");
    expect(formatFullPrecision(1.55, "nm")).toBe("1550");
    expect(formatFullPrecision(1.5e-7, "um")).toBe("1.5e-7");
    expect(formatFullPrecision(-0, "um")).toBe("0");
  });

  it("adds and scales without binary noise", () => {
    expect(1.55 + 0.1).not.toBe(1.65);
    expect(addDecimal(1.55, 0.1)).toBe(1.65);
    expect(0.7 + 0.1).not.toBe(0.8);
    expect(addDecimal(0.7, 0.1)).toBe(0.8);
    expect(0.1 + 0.2).not.toBe(0.3);
    expect(addDecimal(0.1, 0.2)).toBe(0.3);
    expect(addDecimal(1.55, 0.01)).toBe(1.56);
    expect(addDecimal(0.22, -0.01)).toBe(0.21);
    expect(addDecimal(1.5e-7, 1e-8)).toBe(1.6e-7);
    expect(addDecimal(1.234567890123456, 1)).toBe(2.234567890123456);
    expect(addDecimal(1550, -10)).toBe(1540);
    expect(0.07 * 10).not.toBe(0.7);
    expect(scaleDecimal(0.07, 1)).toBe(0.7);
    expect(scaleDecimal(0.01, 0)).toBe(0.01);
  });
});
