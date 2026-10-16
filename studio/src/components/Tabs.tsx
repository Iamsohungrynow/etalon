import * as RadixTabs from "@radix-ui/react-tabs";
import type { ReactNode } from "react";

export interface TabItem<V extends string> {
  value: V;
  label: ReactNode;
  disabled?: boolean;
  /** Why the tab is disabled ("needs M2"), shown as its tooltip. */
  hint?: string;
}

export interface TabsProps<V extends string> {
  /** Accessible name of the tab list. */
  label: string;
  value: V;
  onValueChange: (value: V) => void;
  tabs: readonly TabItem<V>[];
  /** One <TabPanel> per tab. */
  children: ReactNode;
}

/**
 * A row of tabs over panels (Radix Tabs): ←/→ move between tabs and show them,
 * Tab goes into the panel. The active tab has the 2 px accent rule of the header's
 * navigation.
 */
export function Tabs<V extends string>({ label, value, onValueChange, tabs, children }: TabsProps<V>) {
  return (
    <RadixTabs.Root
      value={value}
      onValueChange={(next) => {
        const tab = tabs.find((t) => t.value === next);
        if (tab) onValueChange(tab.value);
      }}
      className="flex min-h-0 flex-1 flex-col"
    >
      <RadixTabs.List
        aria-label={label}
        className="flex h-8 shrink-0 items-stretch gap-5 border-b border-rule bg-surface px-4"
      >
        {tabs.map((tab) => (
          <RadixTabs.Trigger
            key={tab.value}
            value={tab.value}
            disabled={tab.disabled}
            title={tab.disabled ? tab.hint : undefined}
            className="motion flex items-center border-b-2 border-transparent px-1 text-body text-secondary transition-colors enabled:hover:text-text disabled:cursor-not-allowed disabled:text-muted data-[state=active]:border-accent data-[state=active]:text-text"
          >
            {tab.label}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
      {children}
    </RadixTabs.Root>
  );
}
