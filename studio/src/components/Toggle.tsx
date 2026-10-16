import * as Switch from "@radix-ui/react-switch";
import { useId, type ReactNode } from "react";

export interface ToggleProps {
  label: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  help?: ReactNode;
  disabled?: boolean;
}

/** An on/off switch (Radix Switch): Space toggles it, the label is clickable. */
export function Toggle({ label, checked, onCheckedChange, help, disabled }: ToggleProps) {
  const id = useId();
  return (
    <div className="flex items-start gap-3">
      <Switch.Root
        id={id}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        aria-describedby={help ? `${id}-help` : undefined}
        className="motion relative mt-0.5 h-4 w-7 shrink-0 border border-control bg-surface transition-colors data-[state=checked]:border-accent data-[state=checked]:bg-accent disabled:opacity-50"
      >
        <Switch.Thumb className="motion block h-2.5 w-2.5 translate-x-0.5 bg-secondary transition-transform data-[state=checked]:translate-x-3.5 data-[state=checked]:bg-on-accent" />
      </Switch.Root>
      <div className="flex flex-col gap-0.5">
        <label htmlFor={id} className="text-body text-text">
          {label}
        </label>
        {help ? (
          <p id={`${id}-help`} className="text-dense text-secondary">
            {help}
          </p>
        ) : null}
      </div>
    </div>
  );
}
