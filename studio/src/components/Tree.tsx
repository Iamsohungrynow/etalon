import { ChevronRight, Eye, EyeOff } from "lucide-react";
import {
  useId,
  useRef,
  useState,
  type FocusEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { cx } from "./cx";

export interface TreeNode {
  id: string;
  label: ReactNode;
  /** Right-aligned, muted, mono: a refractive index, a count, a kind. */
  meta?: ReactNode;
  icon?: ReactNode;
  children?: TreeNode[];
  /** false for group headings that only expand and collapse (default true). */
  selectable?: boolean;
}

export interface TreeProps {
  /** Accessible name of the tree. */
  label: string;
  nodes: TreeNode[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  hiddenIds?: ReadonlySet<string>;
  /** Gives every leaf an eye toggle (view-only hiding, spec §5.2). */
  onToggleHidden?: (id: string) => void;
  /** Accessible names of the eye toggle: hide a shown item, show a hidden one. */
  hideLabel: string;
  showLabel: string;
}

interface VisibleItem {
  node: TreeNode;
  level: number;
  parentId: string | null;
}

const ROW_PADDING = 8;
const INDENT = 12;

function hasChildren(node: TreeNode): boolean {
  return node.children !== undefined && node.children.length > 0;
}

/** The items a user can see, in order: children of collapsed groups are left out. */
function visibleItems(nodes: TreeNode[], collapsed: ReadonlySet<string>): VisibleItem[] {
  const items: VisibleItem[] = [];
  const walk = (list: TreeNode[], level: number, parentId: string | null) => {
    for (const node of list) {
      items.push({ node, level, parentId });
      if (hasChildren(node) && !collapsed.has(node.id)) walk(node.children ?? [], level + 1, node.id);
    }
  };
  walk(nodes, 0, null);
  return items;
}

/** The ids of the groups that contain `id`, outermost first; empty if it is not in the tree. */
function ancestorsOf(nodes: TreeNode[], id: string): string[] {
  for (const node of nodes) {
    if (node.id === id) return [];
    if (node.children) {
      const inner = ancestorsOf(node.children, id);
      if (inner.length > 0 || node.children.some((child) => child.id === id)) return [node.id, ...inner];
    }
  }
  return [];
}

/**
 * A WAI-ARIA tree (the "tree view" pattern): one tab stop with a roving tabindex,
 * ↑/↓ move, → expands or enters a group, ← collapses or goes to the parent, Home/End,
 * Enter/Space select. Groups start expanded; selecting an item from elsewhere (the
 * viewport) expands the groups around it.
 */
export function Tree({
  label,
  nodes,
  selectedId,
  onSelect,
  hiddenIds,
  onToggleHidden,
  hideLabel,
  showLabel,
}: TreeProps) {
  const baseId = useId();
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(() => new Set());
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(selectedId);
  const itemRefs = useRef(new Map<string, HTMLLIElement>());

  // A new selection from outside: open the groups around it (adjusting state while
  // rendering, as React recommends over an effect).
  if (selectedId !== revealed) {
    setRevealed(selectedId);
    if (selectedId !== null) {
      const around = ancestorsOf(nodes, selectedId).filter((id) => collapsed.has(id));
      if (around.length > 0) setCollapsed(new Set([...collapsed].filter((id) => !around.includes(id))));
    }
  }

  const items = visibleItems(nodes, collapsed);
  const visibleIds = new Set(items.map((item) => item.node.id));
  // Element ids by position, not by node id: a node id may hold a space, which an id list cannot.
  const position = new Map(items.map((item, index) => [item.node.id, index]));
  const activeId =
    (focusedId !== null && visibleIds.has(focusedId) && focusedId) ||
    (selectedId !== null && visibleIds.has(selectedId) && selectedId) ||
    (items[0]?.node.id ?? null);

  const setExpanded = (id: string, expanded: boolean) => {
    const next = new Set(collapsed);
    if (expanded) next.delete(id);
    else next.add(id);
    setCollapsed(next);
  };

  const moveTo = (id: string | undefined) => {
    if (id === undefined) return;
    setFocusedId(id);
    itemRefs.current.get(id)?.focus();
  };

  const activate = (node: TreeNode) => {
    if (node.selectable !== false) onSelect(node.id);
    else if (hasChildren(node)) setExpanded(node.id, collapsed.has(node.id));
  };

  function onKeyDown(event: KeyboardEvent<HTMLUListElement>) {
    const target = event.target as HTMLElement;
    // Keys on the eye toggle are the button's own.
    if (target.getAttribute("role") !== "treeitem") return;
    const index = items.findIndex((item) => item.node.id === target.dataset.id);
    const item = items[index];
    if (item === undefined) return;
    const { node } = item;
    const expandable = hasChildren(node);
    const expanded = expandable && !collapsed.has(node.id);
    let handled = true;
    switch (event.key) {
      case "ArrowDown":
        moveTo(items[index + 1]?.node.id);
        break;
      case "ArrowUp":
        moveTo(items[index - 1]?.node.id);
        break;
      case "ArrowRight":
        if (expandable && !expanded) setExpanded(node.id, true);
        else if (expanded) moveTo(node.children?.[0]?.id);
        break;
      case "ArrowLeft":
        if (expanded) setExpanded(node.id, false);
        else moveTo(item.parentId ?? undefined);
        break;
      case "Home":
        moveTo(items[0]?.node.id);
        break;
      case "End":
        moveTo(items[items.length - 1]?.node.id);
        break;
      case "Enter":
      case " ":
        activate(node);
        break;
      default:
        handled = false;
    }
    if (handled) {
      event.preventDefault();
      event.stopPropagation();
    }
  }

  function onFocus(event: FocusEvent<HTMLUListElement>) {
    const item = (event.target as HTMLElement).closest<HTMLElement>('[role="treeitem"]');
    if (item?.dataset.id !== undefined) setFocusedId(item.dataset.id);
  }

  function onBlur(event: FocusEvent<HTMLUListElement>) {
    // Leaving the tree: the next Tab back in lands on the selected item.
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFocusedId(null);
  }

  function renderNodes(list: TreeNode[], level: number): ReactNode {
    return list.map((node, index) => {
      const expandable = hasChildren(node);
      const expanded = expandable && !collapsed.has(node.id);
      const selectable = node.selectable !== false;
      const selected = selectable && node.id === selectedId;
      const hidden = hiddenIds?.has(node.id) ?? false;
      const active = node.id === activeId;
      const labelId = `${baseId}-${position.get(node.id) ?? 0}-label`;
      const metaId = `${baseId}-${position.get(node.id) ?? 0}-meta`;
      return (
        <li
          key={node.id}
          ref={(element) => {
            if (element) itemRefs.current.set(node.id, element);
            else itemRefs.current.delete(node.id);
          }}
          role="treeitem"
          data-id={node.id}
          tabIndex={active ? 0 : -1}
          aria-level={level + 1}
          aria-setsize={list.length}
          aria-posinset={index + 1}
          aria-expanded={expandable ? expanded : undefined}
          aria-selected={selectable ? selected : undefined}
          aria-labelledby={labelId}
          aria-describedby={node.meta !== undefined ? metaId : undefined}
          className="outline-none [&:focus-visible>div]:outline-2 [&:focus-visible>div]:-outline-offset-2 [&:focus-visible>div]:outline-accent-ink"
        >
          <div
            onClick={() => {
              if (selectable) onSelect(node.id);
              else if (expandable) setExpanded(node.id, !expanded);
            }}
            className={cx(
              "motion flex h-6 cursor-default items-center gap-1.5 border-l-2 pr-1 text-dense transition-colors",
              selected ? "border-accent-ink bg-raised" : "border-transparent hover:bg-hover",
              hidden ? "text-muted" : "text-text",
            )}
            style={{ paddingLeft: ROW_PADDING - 2 + level * INDENT }}
          >
            {expandable ? (
              <span
                aria-hidden
                data-testid="tree-chevron"
                onClick={(event) => {
                  event.stopPropagation();
                  setExpanded(node.id, !expanded);
                }}
                className="flex w-3.5 shrink-0 justify-center text-muted"
              >
                <ChevronRight size={14} className={cx("motion transition-transform", expanded && "rotate-90")} />
              </span>
            ) : (
              <span aria-hidden className="w-3.5 shrink-0" />
            )}
            {node.icon ? (
              <span aria-hidden className={cx("flex shrink-0", hidden ? "text-muted" : "text-secondary")}>
                {node.icon}
              </span>
            ) : null}
            <span id={labelId} className="min-w-0 flex-1 truncate">
              {node.label}
            </span>
            {node.meta !== undefined ? (
              <span id={metaId} className="shrink-0 font-mono whitespace-nowrap text-muted tabular-nums">
                {node.meta}
              </span>
            ) : null}
            {onToggleHidden && !expandable ? (
              <button
                type="button"
                tabIndex={active ? 0 : -1}
                aria-label={hidden ? showLabel : hideLabel}
                title={hidden ? showLabel : hideLabel}
                onClick={(event) => {
                  event.stopPropagation();
                  onToggleHidden(node.id);
                }}
                className="motion inline-flex h-5 w-5 shrink-0 items-center justify-center border border-transparent text-muted transition-colors hover:bg-hover hover:text-text"
              >
                {hidden ? <EyeOff size={14} aria-hidden /> : <Eye size={14} aria-hidden />}
              </button>
            ) : null}
          </div>
          {expanded ? (
            <ul role="group">{renderNodes(node.children ?? [], level + 1)}</ul>
          ) : null}
        </li>
      );
    });
  }

  return (
    <ul
      role="tree"
      aria-label={label}
      onKeyDown={onKeyDown}
      onFocus={onFocus}
      onBlur={onBlur}
      className="flex flex-col select-none"
    >
      {renderNodes(nodes, 0)}
    </ul>
  );
}
