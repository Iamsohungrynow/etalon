import type { ReactNode } from "react";

interface KitchenSectionProps {
  title: string;
  children: ReactNode;
}

/** One labelled group of components on the kitchen-sink page. */
export function KitchenSection({ title, children }: KitchenSectionProps) {
  return (
    <section className="flex flex-col gap-3 border-b border-rule-subtle px-4 py-4">
      <h2 className="micro-label">{title}</h2>
      <div className="flex flex-wrap items-start gap-4">{children}</div>
    </section>
  );
}
