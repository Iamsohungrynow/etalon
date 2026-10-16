import * as ToggleGroup from "@radix-ui/react-toggle-group";
import type { ReactNode } from "react";

export interface SegmentedOption<V extends string> {
  value: V;
  label: ReactNode;
}

export interface SegmentedProps<V extends string> {
  /** Accessible name of the group. */
  label: string;
  value: V;
  options: readonly SegmentedOption<V>[];
  onValueChange: (value: V) => void;
  disabled?: boolean;
}

/** One-of-N choice (Radix ToggleGroup): arrow keys move, Space/Enter picks. */
export function Segmented<V extends string>({
  label,
  value,
  options,
  onValueChange,
  disabled,
}: SegmentedProps<V>) {
  return (
    <ToggleGroup.Root
      type="single"
      aria-label={label}
      value={value}
      disabled={disabled}
      // Radix reports "" when the active item is pressed again; a segmented control
      // always has a value, so that is ignored.
      onValueChange={(next) => {
        const option = options.find((o) => o.value === next);
        if (option) onValueChange(option.value);
      }}
      className="inline-flex border border-control"
    >
      {options.map((option) => (
        <ToggleGroup.Item
          key={option.value}
          value={option.value}
          className="motion h-7 border-l border-control px-3 text-body text-secondary transition-colors first:border-l-0 hover:bg-hover hover:text-text data-[state=on]:bg-accent data-[state=on]:text-on-accent disabled:opacity-50"
        >
          {option.label}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}
