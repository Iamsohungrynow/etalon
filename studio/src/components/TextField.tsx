import { useId, type InputHTMLAttributes, type ReactNode } from "react";
import { cx } from "./cx";

export interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  label: string;
  /** Keep the label for screen readers only (e.g. a filter box with a search icon). */
  hideLabel?: boolean;
  help?: ReactNode;
  error?: string | null;
  icon?: ReactNode;
  mono?: boolean;
}

export function TextField({
  label,
  hideLabel = false,
  help,
  error,
  icon,
  mono = false,
  className,
  id,
  ...rest
}: TextFieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const helpId = `${inputId}-help`;
  const errorId = `${inputId}-error`;
  const describedBy = [help ? helpId : null, error ? errorId : null].filter(Boolean).join(" ");
  return (
    <div className={cx("flex min-w-0 flex-col gap-1", className)}>
      <label htmlFor={inputId} className={hideLabel ? "sr-only" : "micro-label"}>
        {label}
      </label>
      <div
        className={cx(
          "flex h-7 min-w-0 items-center gap-1.5 border bg-surface px-2 focus-within:outline-2 focus-within:outline-accent-ink",
          error ? "border-error" : "border-control",
        )}
      >
        {icon ? (
          <span aria-hidden className="text-muted">
            {icon}
          </span>
        ) : null}
        <input
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy || undefined}
          className={cx(
            "h-full min-w-0 flex-1 bg-transparent text-body text-text outline-none placeholder:text-muted",
            mono && "font-mono text-dense",
          )}
          {...rest}
        />
      </div>
      {help ? (
        <p id={helpId} className="text-dense text-secondary">
          {help}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-dense text-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
