import * as RadixSelect from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import type { ReactNode } from "react";

export interface SelectOption<V extends string> {
  value: V;
  label: ReactNode;
  disabled?: boolean;
}

export interface SelectProps<V extends string> {
  /** Accessible name of the trigger. */
  label: string;
  value: V;
  options: readonly SelectOption<V>[];
  onValueChange: (value: V) => void;
  disabled?: boolean;
  id?: string;
}

/** A dropdown (Radix Select): keyboard-complete, rendered in a portal. */
export function Select<V extends string>({
  label,
  value,
  options,
  onValueChange,
  disabled,
  id,
}: SelectProps<V>) {
  return (
    <RadixSelect.Root
      value={value}
      disabled={disabled}
      onValueChange={(next) => {
        const option = options.find((o) => o.value === next);
        if (option) onValueChange(option.value);
      }}
    >
      <RadixSelect.Trigger
        id={id}
        aria-label={label}
        className="motion inline-flex h-7 min-w-56 items-center justify-between gap-2 border border-control bg-surface px-2 text-left text-body text-text transition-colors hover:bg-hover disabled:opacity-50"
      >
        <RadixSelect.Value />
        <RadixSelect.Icon className="text-muted">
          <ChevronDown size={16} aria-hidden />
        </RadixSelect.Icon>
      </RadixSelect.Trigger>
      <RadixSelect.Portal>
        <RadixSelect.Content
          position="popper"
          sideOffset={2}
          className="z-50 min-w-[var(--radix-select-trigger-width)] border border-rule bg-surface text-body text-text"
        >
          <RadixSelect.Viewport className="p-0.5">
            {options.map((option) => (
              <RadixSelect.Item
                key={option.value}
                value={option.value}
                disabled={option.disabled}
                className="flex h-7 cursor-default items-center gap-2 px-2 outline-none select-none data-[disabled]:opacity-50 data-[highlighted]:bg-hover"
              >
                <span className="w-4 text-accent-ink">
                  <RadixSelect.ItemIndicator>
                    <Check size={14} aria-hidden />
                  </RadixSelect.ItemIndicator>
                </span>
                <RadixSelect.ItemText>{option.label}</RadixSelect.ItemText>
              </RadixSelect.Item>
            ))}
          </RadixSelect.Viewport>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  );
}
