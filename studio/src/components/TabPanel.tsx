import * as RadixTabs from "@radix-ui/react-tabs";
import type { ReactNode } from "react";

export interface TabPanelProps {
  /** The value of the tab that shows this panel. */
  value: string;
  children: ReactNode;
}

/** The content of one tab; only the active panel is in the DOM. Use inside <Tabs>. */
export function TabPanel({ value, children }: TabPanelProps) {
  return (
    <RadixTabs.Content value={value} className="flex min-h-0 flex-1 flex-col focus-visible:-outline-offset-2">
      {children}
    </RadixTabs.Content>
  );
}
