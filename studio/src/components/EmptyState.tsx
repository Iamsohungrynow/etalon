import type { ReactNode } from "react";

export interface EmptyStateProps {
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
}

/** Nothing to show yet: a short explanation and what to do. No illustration (spec §5.1). */
export function EmptyState({ title, children, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-start gap-3 px-4 py-10">
      <h2 className="text-h3 font-semibold text-text">{title}</h2>
      {children ? <div className="max-w-[60ch] text-body text-secondary">{children}</div> : null}
      {action}
    </div>
  );
}
