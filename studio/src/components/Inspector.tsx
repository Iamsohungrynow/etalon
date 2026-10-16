import { Fragment, type ReactNode } from "react";
import { Value } from "./Value";

export interface InspectorRow {
  key: string;
  label: ReactNode;
  value: ReactNode;
}

export interface InspectorProps {
  rows: readonly InspectorRow[];
  /** Shown when there are no rows (nothing selected). */
  emptyText?: string;
}

/** Read-only properties of the selection (spec §5.2): label in secondary, value in mono. */
export function Inspector({ rows, emptyText }: InspectorProps) {
  if (rows.length === 0) {
    return emptyText ? <p className="text-dense text-muted">{emptyText}</p> : null;
  }
  return (
    <dl className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-x-3 gap-y-1 text-dense">
      {rows.map((row) => (
        <Fragment key={row.key}>
          <dt className="min-w-0 truncate text-secondary">{row.label}</dt>
          <dd className="min-w-0 text-text wrap-anywhere">
            <Value>{row.value}</Value>
          </dd>
        </Fragment>
      ))}
    </dl>
  );
}
