import { useLayoutEffect, useRef } from "react";
import { cx } from "./cx";

export type LogStream = "stdout" | "stderr" | "etalon";

export interface LogLine {
  stream: LogStream;
  line: string;
}

export interface LogViewProps {
  /** Accessible name of the log region. */
  label: string;
  lines: readonly LogLine[];
  /** Shown while there are no lines. */
  emptyText: string;
  /** Keep the newest line in view while the user has not scrolled up (default true). */
  follow?: boolean;
}

/** The DOM keeps the newest lines only; the full log stays in the result's folder. */
const MAX_LINES = 2000;
/** Within this many pixels of the bottom counts as "at the bottom". */
const STICK_PX = 4;

const STREAMS: Record<LogStream, string> = {
  stdout: "text-text",
  stderr: "text-error",
  etalon: "text-secondary",
};

/**
 * A script's output (spec §5.3): mono 12 px on the page background, stderr in the error
 * colour, etalon's own lines in secondary. It follows new lines until the user scrolls
 * up, and again once they scroll back to the bottom. aria-live is off: a screen reader
 * reading every solver step aloud would be unusable.
 */
export function LogView({ label, lines, emptyText, follow = true }: LogViewProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const atBottom = useRef(true);
  const first = Math.max(0, lines.length - MAX_LINES);
  const shown = first > 0 ? lines.slice(first) : lines;

  useLayoutEffect(() => {
    const element = scrollRef.current;
    if (element && follow && atBottom.current) element.scrollTop = element.scrollHeight;
  }, [lines, follow]);

  return (
    <div
      ref={scrollRef}
      role="log"
      aria-label={label}
      aria-live="off"
      tabIndex={0}
      translate="no"
      onScroll={(event) => {
        const element = event.currentTarget;
        atBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight <= STICK_PX;
      }}
      className="min-h-0 flex-1 overflow-auto bg-bg px-3 py-2 font-mono text-dense"
    >
      {shown.length === 0 ? (
        <p className="font-sans text-muted" translate="yes">
          {emptyText}
        </p>
      ) : (
        shown.map((entry, index) => (
          <div
            key={first + index}
            data-stream={entry.stream}
            className={cx("whitespace-pre-wrap wrap-anywhere", STREAMS[entry.stream])}
          >
            {entry.line}
          </div>
        ))
      )}
    </div>
  );
}
