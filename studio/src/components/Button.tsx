import { Slot, Slottable } from "@radix-ui/react-slot";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cx } from "./cx";

export type ButtonVariant = "primary" | "secondary" | "ghost";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  icon?: ReactNode;
  /** Render the child (e.g. a router <Link>) with button styling instead of a <button>. */
  asChild?: boolean;
}

export const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: "border-accent bg-accent text-on-accent hover:brightness-110",
  secondary: "border-control bg-surface text-text hover:bg-hover",
  ghost: "border-transparent bg-transparent text-secondary hover:bg-hover hover:text-text",
};

export function Button({
  variant = "secondary",
  icon,
  asChild = false,
  className,
  children,
  type,
  ...rest
}: ButtonProps) {
  const Component = asChild ? Slot : "button";
  return (
    <Component
      type={asChild ? undefined : (type ?? "button")}
      className={cx(
        "motion inline-flex h-7 shrink-0 items-center gap-1.5 border px-3 text-body font-medium whitespace-nowrap transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50",
        BUTTON_VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {icon}
      <Slottable>{children}</Slottable>
    </Component>
  );
}
