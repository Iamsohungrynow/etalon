import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef, type ReactNode } from "react";
import { cx } from "./cx";

export interface Column<Row> {
  id: string;
  header: ReactNode;
  /** A CSS grid track, e.g. "minmax(0, 2fr)" or "7rem". */
  width: string;
  align?: "start" | "end";
  cell: (row: Row) => ReactNode;
}

export interface TableProps<Row> {
  /** Accessible name of the table. */
  label: string;
  columns: readonly Column<Row>[];
  rows: readonly Row[];
  rowKey: (row: Row) => string;
  rowHeight?: number;
  /** Height assumed before the first layout measurement (jsdom has none). */
  initialHeight?: number;
}

const HEADER_HEIGHT = 28;

/**
 * A dense, virtualised table: only the rows in view are in the DOM, so 5 000 scripts
 * scroll as smoothly as 50. ARIA table roles keep it a table for screen readers,
 * with aria-rowcount/aria-rowindex covering the rows that are not rendered.
 */
export function Table<Row>({
  label,
  columns,
  rows,
  rowKey,
  rowHeight = 28,
  initialHeight = 800,
}: TableProps<Row>) {
  const scrollRef = useRef<HTMLDivElement>(null);
  // Studio does not use the React Compiler, so its "cannot memoize" notice does not apply.
  // eslint-disable-next-line react-hooks/incompatible-library
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => rowHeight,
    overscan: 12,
    scrollMargin: HEADER_HEIGHT,
    initialRect: { width: 1024, height: initialHeight },
  });
  const template = { gridTemplateColumns: columns.map((c) => c.width).join(" ") };
  return (
    <div
      ref={scrollRef}
      role="table"
      aria-label={label}
      aria-rowcount={rows.length + 1}
      data-testid="table-scroll"
      className="min-h-0 flex-1 overflow-y-auto"
    >
      <div role="rowgroup" className="sticky top-0 z-10">
        <div
          role="row"
          aria-rowindex={1}
          className="grid items-center gap-3 border-b border-rule bg-surface px-4"
          style={{ ...template, height: HEADER_HEIGHT }}
        >
          {columns.map((column) => (
            <div
              key={column.id}
              role="columnheader"
              className={cx("micro-label truncate", column.align === "end" && "text-right")}
            >
              {column.header}
            </div>
          ))}
        </div>
      </div>
      <div
        role="rowgroup"
        className="relative"
        style={{ height: virtualizer.getTotalSize() }}
      >
        {virtualizer.getVirtualItems().map((item) => {
          const row = rows[item.index];
          if (row === undefined) return null;
          return (
            <div
              key={rowKey(row)}
              role="row"
              aria-rowindex={item.index + 2}
              // A focused link inside the row rings the whole row (the link covers it).
              className="absolute right-0 left-0 grid items-center gap-3 border-b border-rule-subtle px-4 text-dense focus-within:bg-hover hover:bg-hover has-[:focus-visible]:outline-2 has-[:focus-visible]:-outline-offset-2 has-[:focus-visible]:outline-accent-ink"
              style={{
                ...template,
                height: rowHeight,
                transform: `translateY(${item.start - HEADER_HEIGHT}px)`,
              }}
            >
              {columns.map((column) => (
                <div
                  key={column.id}
                  role="cell"
                  className={cx("min-w-0 truncate", column.align === "end" && "text-right")}
                >
                  {column.cell(row)}
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
