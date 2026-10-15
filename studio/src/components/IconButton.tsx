import type { ButtonHTMLAttributes, ReactNode } from "react";
import { BUTTON_VARIANTS, type ButtonVariant } from "./Button";
import { cx } from "./cx";

export interface IconButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-label" | "children"> {
  /** Required: an icon alone has no text, so this is its accessible name and tooltip. */
  label: string;
  icon: ReactNode;
  variant?: ButtonVariant;
}

export function IconButton({
  label,
  icon,
  variant = "ghost",
  className,
  type,
  ...rest
}: IconButtonProps) {
  return (
    <button
      type={type ?? "button"}
      aria-label={label}
      title={label}
      className={cx(
        "motion inline-flex h-7 w-7 shrink-0 items-center justify-center border transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50",
        BUTTON_VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {icon}
    </button>
  );
}
