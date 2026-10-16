import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {
  addDecimal,
  formatFullPrecision,
  formatQuantity,
  fromApiUnits,
  parseQuantity,
  scaleDecimal,
  toApiUnits,
  unitSymbol,
  type Quantity,
  type Unit,
} from "../format/units";
import { cx } from "./cx";
import { Value } from "./Value";

export interface NumberFieldProps {
  label: string;
  /** Keep the label for screen readers only (e.g. inside an Inspector row that has its own). */
  hideLabel?: boolean;
  /** In API units: µm, s or Hz (CLAUDE.md "Units"). */
  value: number;
  quantity: Quantity;
  /** The unit shown, and the unit of a bare number typed in. */
  displayUnit: Unit;
  /** Called with the new value in API units on Enter, blur or an arrow-key step. */
  onCommit?: (value: number) => void;
  /** A plain mono value under its label, for the Inspector. */
  readOnly?: boolean;
  /** Bounds in API units, inclusive. */
  min?: number;
  max?: number;
  /** Arrow-key step in `displayUnit` (Shift: ×10). Without it the arrows only move the caret. */
  step?: number;
  /** Shown when the text is not a number of this quantity. */
  invalidMessage: string;
  /** Shown when the number is outside [min, max]; falls back to invalidMessage. */
  rangeMessage?: string;
  help?: ReactNode;
}

type Problem = "invalid" | "range" | null;

function clamp(value: number, min: number | undefined, max: number | undefined): number {
  if (min !== undefined && value < min) return min;
  if (max !== undefined && value > max) return max;
  return value;
}

/**
 * A unit-aware number input (plan-u1 §5). Shows 4 significant figures with the unit;
 * on focus the full-precision value. Enter or blur parses ("1550nm", "1.55e-6 m", "1,55")
 * and commits in API units; Escape reverts; ↑/↓ step, Shift ×10. A bad entry stays in the
 * field with its message underneath until it is fixed or reverted.
 */
export function NumberField({
  label,
  hideLabel = false,
  value,
  quantity,
  displayUnit,
  onCommit,
  readOnly = false,
  min,
  max,
  step,
  invalidMessage,
  rangeMessage,
  help,
}: NumberFieldProps) {
  const { i18n } = useTranslation();
  const id = useId();
  const helpId = `${id}-help`;
  const errorId = `${id}-error`;
  const inputRef = useRef<HTMLInputElement>(null);
  /** The text being edited; null shows the formatted value. */
  const [draft, setDraft] = useState<string | null>(null);
  /** The text of the last committed value: leaving it unchanged commits nothing. */
  const [baseline, setBaseline] = useState("");
  const [problem, setProblem] = useState<Problem>(null);
  const [focused, setFocused] = useState(false);

  // Select the full-precision text once it is in the input, so typing replaces it.
  useEffect(() => {
    if (focused) inputRef.current?.select();
  }, [focused]);

  const symbol = unitSymbol(displayUnit);
  const editText = (v: number) => `${formatFullPrecision(v, displayUnit)} ${symbol}`;
  const formatted = formatQuantity(value, quantity, displayUnit, i18n.language);

  if (readOnly) {
    return (
      <div className="flex min-w-0 flex-col gap-1">
        <span className={hideLabel ? "sr-only" : "micro-label"}>{label}</span>
        <Value title={editText(value)} className="text-dense text-text">
          {formatted}
        </Value>
        {help ? <p className="text-dense text-secondary">{help}</p> : null}
      </div>
    );
  }

  /** Parse the text and commit it if it changed; the normalised text, or null if it is bad. */
  function commit(text: string): string | null {
    if (text === baseline) {
      setProblem(null);
      return baseline;
    }
    const parsed = parseQuantity(text, quantity, displayUnit);
    if (parsed === null) {
      setProblem("invalid");
      return null;
    }
    if (clamp(parsed, min, max) !== parsed) {
      setProblem("range");
      return null;
    }
    const next = editText(parsed);
    setProblem(null);
    setBaseline(next);
    if (parsed !== value) onCommit?.(parsed);
    return next;
  }

  function stepBy(direction: 1 | -1, large: boolean) {
    if (step === undefined) return;
    const base = parseQuantity(draft ?? "", quantity, displayUnit);
    const start = base !== null && clamp(base, min, max) === base ? base : value;
    const delta = scaleDecimal(step, large ? 1 : 0) * direction;
    const next = clamp(toApiUnits(addDecimal(fromApiUnits(start, displayUnit), delta), displayUnit), min, max);
    setProblem(null);
    setDraft(editText(next));
    setBaseline(editText(next));
    if (next !== value) onCommit?.(next);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      const next = commit(draft ?? baseline);
      if (next !== null) setDraft(next);
    } else if (event.key === "Escape") {
      const reverted = editText(value);
      if (draft !== reverted || problem !== null) {
        // Something to undo: keep Escape from also closing a dialog around the field.
        event.preventDefault();
        event.stopPropagation();
        setDraft(reverted);
        setBaseline(reverted);
        setProblem(null);
      }
    } else if ((event.key === "ArrowUp" || event.key === "ArrowDown") && step !== undefined) {
      event.preventDefault();
      stepBy(event.key === "ArrowUp" ? 1 : -1, event.shiftKey);
    }
  }

  const message = problem === "range" ? (rangeMessage ?? invalidMessage) : problem ? invalidMessage : null;
  const describedBy = [help ? helpId : null, message ? errorId : null].filter(Boolean).join(" ");
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <label htmlFor={id} className={hideLabel ? "sr-only" : "micro-label"}>
        {label}
      </label>
      <div
        className={cx(
          "flex h-7 min-w-0 items-center border bg-surface px-2 focus-within:outline-2 focus-within:outline-accent-ink",
          message ? "border-error" : "border-control",
        )}
      >
        <input
          ref={inputRef}
          id={id}
          type="text"
          autoComplete="off"
          spellCheck={false}
          translate="no"
          value={draft ?? formatted}
          title={draft === null ? editText(value) : undefined}
          aria-invalid={message ? true : undefined}
          aria-describedby={describedBy || undefined}
          onFocus={() => {
            setFocused(true);
            if (draft === null) {
              setDraft(editText(value));
              setBaseline(editText(value));
            }
          }}
          onBlur={() => {
            setFocused(false);
            if (draft === null) return;
            if (commit(draft) !== null) setDraft(null);
          }}
          onChange={(event) => {
            setDraft(event.target.value);
          }}
          onKeyDown={onKeyDown}
          className="h-full min-w-0 flex-1 bg-transparent font-mono text-dense text-text tabular-nums outline-none"
        />
      </div>
      {help ? (
        <p id={helpId} className="text-dense text-secondary">
          {help}
        </p>
      ) : null}
      {message ? (
        <p id={errorId} className="text-dense text-error">
          {message}
        </p>
      ) : null}
    </div>
  );
}
