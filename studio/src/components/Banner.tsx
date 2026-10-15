import { CircleAlert, Info, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "./cx";

export type BannerTone = "info" | "warn" | "error";

export interface BannerProps {
  tone?: BannerTone;
  children: ReactNode;
  /** A link or button at the end of the line. */
  action?: ReactNode;
}

const ICONS = { info: Info, warn: TriangleAlert, error: CircleAlert } as const;
const TONES: Record<BannerTone, string> = {
  info: "text-secondary",
  warn: "text-warn",
  error: "text-error",
};

/** A one-line, non-blocking notice under a toolbar. Never used for transient events. */
export function Banner({ tone = "info", children, action }: BannerProps) {
  const Icon = ICONS[tone];
  return (
    <div
      role="status"
      className="flex items-center gap-2 border-b border-rule bg-raised px-4 py-1.5 text-dense"
    >
      <Icon size={16} aria-hidden className={cx("shrink-0", TONES[tone])} />
      <span className="min-w-0 flex-1 text-text">{children}</span>
      {action}
    </div>
  );
}
