// U1 design-system components: NumberField, Tree, Tabs, ProgressBar, LogView, Inspector.
import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Box } from "lucide-react";
import { useState, type ReactElement } from "react";
import { I18nextProvider } from "react-i18next";
import { describe, expect, it, vi } from "vitest";
import { renderWithI18n } from "../test/renderApp";
import { Inspector } from "./Inspector";
import { LogView, type LogLine } from "./LogView";
import { NumberField, type NumberFieldProps } from "./NumberField";
import { ProgressBar } from "./ProgressBar";
import { TabPanel } from "./TabPanel";
import { Tabs } from "./Tabs";
import { Tree, type TreeNode } from "./Tree";

/**
 * renderWithI18n whose rerender keeps the provider: a bare rerender(ui) would swap the root
 * and remount the component, losing its state and DOM node.
 */
function renderKeepingState(ui: ReactElement) {
  const result = renderWithI18n(ui);
  const rerender = (next: ReactElement) =>
    result.rerender(<I18nextProvider i18n={result.i18n}>{next}</I18nextProvider>);
  return { ...result, rerender };
}

const INVALID = "Enter a length, e.g. 1.55 µm.";
const RANGE = "Between 0 and 10 µm.";

/** A NumberField whose value follows its commits, as a screen would wire it. */
function Controlled(props: Partial<NumberFieldProps> & { onCommitSpy: (value: number) => void }) {
  const { onCommitSpy, ...rest } = props;
  const [value, setValue] = useState(rest.value ?? 1.5500001);
  return (
    <NumberField
      label="Wavelength"
      quantity="length"
      displayUnit="um"
      invalidMessage={INVALID}
      {...rest}
      value={value}
      onCommit={(next) => {
        setValue(next);
        onCommitSpy(next);
      }}
    />
  );
}

describe("NumberField", () => {
  it("shows 4 significant figures, full precision on focus, and commits on Enter", async () => {
    const onCommit = vi.fn();
    renderWithI18n(<Controlled onCommitSpy={onCommit} />);
    const input = screen.getByRole("textbox", { name: "Wavelength" });
    expect(input).toHaveValue("1.55 µm");
    expect(input).toHaveAttribute("title", "1.5500001 µm");
    await userEvent.click(input);
    expect(input).toHaveValue("1.5500001 µm");
    await userEvent.clear(input);
    await userEvent.type(input, "1600nm{Enter}");
    expect(onCommit).toHaveBeenCalledExactlyOnceWith(1.6);
    expect(input).toHaveFocus();
    expect(input).toHaveValue("1.6 µm");
    await userEvent.tab();
    expect(input).toHaveValue("1.6 µm");
    expect(onCommit).toHaveBeenCalledOnce(); // blurring an unchanged value commits nothing
  });

  it("commits on blur, accepts units and comma decimals", async () => {
    const onCommit = vi.fn();
    renderWithI18n(<Controlled onCommitSpy={onCommit} displayUnit="nm" value={1.55} />);
    const input = screen.getByRole("textbox", { name: "Wavelength" });
    expect(input).toHaveValue("1550 nm");
    await userEvent.clear(input);
    await userEvent.type(input, "1,31 µm");
    await userEvent.tab();
    expect(onCommit).toHaveBeenCalledExactlyOnceWith(1.31);
    expect(input).toHaveValue("1310 nm");
    await userEvent.clear(input);
    await userEvent.type(input, "1500"); // a bare number is in the display unit
    await userEvent.tab();
    expect(onCommit).toHaveBeenLastCalledWith(1.5);
  });

  it("reverts on Escape", async () => {
    const onCommit = vi.fn();
    renderWithI18n(<Controlled onCommitSpy={onCommit} />);
    const input = screen.getByRole("textbox", { name: "Wavelength" });
    await userEvent.clear(input);
    await userEvent.type(input, "abc{Enter}");
    expect(input).toHaveAttribute("aria-invalid", "true");
    await userEvent.keyboard("{Escape}");
    expect(input).toHaveValue("1.5500001 µm");
    expect(input).not.toHaveAttribute("aria-invalid");
    expect(screen.queryByText(INVALID)).not.toBeInTheDocument();
    await userEvent.tab();
    expect(input).toHaveValue("1.55 µm");
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("steps with the arrow keys in the display unit, ×10 with Shift, within bounds", async () => {
    const onCommit = vi.fn();
    renderWithI18n(<Controlled onCommitSpy={onCommit} displayUnit="nm" value={1.55} step={1} max={1.6} />);
    const input = screen.getByRole("textbox", { name: "Wavelength" });
    await userEvent.click(input);
    await userEvent.keyboard("{ArrowUp}");
    expect(onCommit).toHaveBeenLastCalledWith(1.551);
    expect(input).toHaveValue("1551 nm");
    await userEvent.keyboard("{Shift>}{ArrowDown}{/Shift}");
    expect(onCommit).toHaveBeenLastCalledWith(1.541);
    await userEvent.keyboard("{ArrowDown}");
    expect(onCommit).toHaveBeenLastCalledWith(1.54);
    for (let i = 0; i < 7; i += 1) await userEvent.keyboard("{Shift>}{ArrowUp}{/Shift}");
    expect(onCommit).toHaveBeenLastCalledWith(1.6); // clamped at max
    expect(input).toHaveValue("1600 nm");
  });

  it("steps decimals without binary noise", async () => {
    const onCommit = vi.fn();
    renderWithI18n(<Controlled onCommitSpy={onCommit} value={1.55} step={0.1} />);
    const input = screen.getByRole("textbox", { name: "Wavelength" });
    await userEvent.click(input);
    await userEvent.keyboard("{ArrowUp}");
    expect(onCommit).toHaveBeenLastCalledWith(1.65); // 1.55 + 0.1 is 1.6500000000000001
    expect(input).toHaveValue("1.65 µm");
  });

  it("leaves the arrows alone without a step", async () => {
    const onCommit = vi.fn();
    renderWithI18n(<Controlled onCommitSpy={onCommit} />);
    await userEvent.click(screen.getByRole("textbox", { name: "Wavelength" }));
    await userEvent.keyboard("{ArrowUp}{ArrowDown}");
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("shows an invalid entry inline and keeps it until fixed", async () => {
    const onCommit = vi.fn();
    renderWithI18n(<Controlled onCommitSpy={onCommit} help="Vacuum wavelength." />);
    const input = screen.getByRole("textbox", { name: "Wavelength" });
    expect(input).toHaveAccessibleDescription("Vacuum wavelength.");
    for (const bad of ["1.55 kg", "1.55 fs", "abc"]) {
      await userEvent.clear(input);
      await userEvent.type(input, `${bad}{Enter}`);
      expect(input).toHaveAttribute("aria-invalid", "true");
      expect(input).toHaveAccessibleDescription(`Vacuum wavelength. ${INVALID}`);
    }
    await userEvent.tab();
    expect(input).toHaveValue("abc"); // the bad text stays, with its message
    expect(screen.getByText(INVALID)).toHaveClass("text-error");
    await userEvent.clear(input);
    await userEvent.type(input, "1.31{Enter}");
    expect(input).not.toHaveAttribute("aria-invalid");
    expect(onCommit).toHaveBeenCalledExactlyOnceWith(1.31);
  });

  it("shows the range message outside [min, max]", async () => {
    const onCommit = vi.fn();
    renderWithI18n(<Controlled onCommitSpy={onCommit} min={0} max={10} rangeMessage={RANGE} />);
    const input = screen.getByRole("textbox", { name: "Wavelength" });
    await userEvent.clear(input);
    await userEvent.type(input, "20{Enter}");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription(RANGE);
    await userEvent.clear(input);
    await userEvent.type(input, "-1{Enter}");
    expect(input).toHaveAccessibleDescription(RANGE);
    await userEvent.clear(input);
    await userEvent.type(input, "10000 nm{Enter}"); // exactly max: inclusive
    expect(input).not.toHaveAttribute("aria-invalid");
    expect(onCommit).toHaveBeenCalledExactlyOnceWith(10);
  });

  it("falls back to the invalid message without a range message", async () => {
    renderWithI18n(<Controlled onCommitSpy={vi.fn()} max={10} />);
    const input = screen.getByRole("textbox", { name: "Wavelength" });
    await userEvent.clear(input);
    await userEvent.type(input, "20{Enter}");
    expect(input).toHaveAccessibleDescription(INVALID);
  });

  it("renders read-only as a plain mono value under its label", () => {
    renderWithI18n(
      <NumberField
        label="Slab"
        readOnly
        value={0.11}
        quantity="length"
        displayUnit="nm"
        invalidMessage={INVALID}
      />,
    );
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByText("Slab")).toHaveClass("micro-label");
    const value = screen.getByText("110 nm");
    expect(value).toHaveAttribute("translate", "no");
    expect(value).toHaveClass("font-mono");
    expect(value).toHaveAttribute("title", "110 nm");
  });

  it("keeps a hidden label for screen readers", () => {
    renderWithI18n(
      <NumberField label="Radius" hideLabel value={10} quantity="length" displayUnit="um" invalidMessage={INVALID} />,
    );
    expect(screen.getByRole("textbox", { name: "Radius" })).toHaveValue("10 µm");
    expect(screen.getByText("Radius")).toHaveClass("sr-only");
  });
});

const NODES: TreeNode[] = [
  {
    id: "group:media",
    label: "Media",
    selectable: false,
    children: [
      { id: "si", label: "si", meta: "3.476" },
      { id: "sio2", label: "sio2", meta: "1.444" },
    ],
  },
  {
    id: "group:structures",
    label: "Structures",
    selectable: false,
    children: [
      { id: "bus_wg", label: "bus_wg", icon: <Box size={14} /> },
      { id: "ring", label: "ring" },
    ],
  },
  { id: "boundary", label: "Boundary", meta: "PML 12" },
];

function ControlledTree({
  onSelectSpy,
  onToggleSpy,
  initialSelected = null,
}: {
  onSelectSpy?: (id: string) => void;
  onToggleSpy?: (id: string) => void;
  initialSelected?: string | null;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(initialSelected);
  const [hidden, setHidden] = useState<ReadonlySet<string>>(new Set(["sio2"]));
  return (
    <>
      <button type="button">before</button>
      <Tree
        label="Structure"
        nodes={NODES}
        selectedId={selectedId}
        onSelect={(id) => {
          setSelectedId(id);
          onSelectSpy?.(id);
        }}
        hiddenIds={hidden}
        onToggleHidden={(id) => {
          const next = new Set(hidden);
          if (next.has(id)) next.delete(id);
          else next.add(id);
          setHidden(next);
          onToggleSpy?.(id);
        }}
        hideLabel="Hide"
        showLabel="Show"
      />
    </>
  );
}

const item = (name: string) => screen.getByRole("treeitem", { name });

describe("Tree", () => {
  it("is a WAI-ARIA tree: groups expanded, selection marked, one tab stop", async () => {
    renderWithI18n(<ControlledTree initialSelected="ring" />);
    const tree = screen.getByRole("tree", { name: "Structure" });
    expect(within(tree).getAllByRole("treeitem")).toHaveLength(7);
    expect(within(tree).getAllByRole("group")).toHaveLength(2);
    expect(item("Media")).toHaveAttribute("aria-expanded", "true");
    expect(item("Media")).not.toHaveAttribute("aria-selected");
    expect(item("si")).not.toHaveAttribute("aria-expanded");
    expect(item("si")).toHaveAttribute("aria-level", "2");
    expect(item("si")).toHaveAccessibleDescription("3.476");
    expect(item("ring")).toHaveAttribute("aria-selected", "true");
    expect(item("bus_wg")).toHaveAttribute("aria-selected", "false");
    const tabStops = within(tree)
      .getAllByRole("treeitem")
      .filter((el) => el.tabIndex === 0);
    expect(tabStops).toEqual([item("ring")]);
    await userEvent.click(screen.getByRole("button", { name: "before" }));
    await userEvent.tab();
    expect(item("ring")).toHaveFocus(); // Tab lands on the selected item
    expect(item("ring").firstElementChild).toHaveClass("bg-raised", "border-accent-ink");
  });

  it("moves with ↑/↓/Home/End and selects with Enter and Space", async () => {
    const onSelect = vi.fn();
    renderWithI18n(<ControlledTree onSelectSpy={onSelect} />);
    await userEvent.click(screen.getByRole("button", { name: "before" }));
    await userEvent.tab();
    expect(item("Media")).toHaveFocus(); // nothing selected: the first item
    await userEvent.keyboard("{ArrowDown}");
    expect(item("si")).toHaveFocus();
    expect(item("si")).toHaveAttribute("tabindex", "0");
    expect(item("Media")).toHaveAttribute("tabindex", "-1");
    await userEvent.keyboard("{Enter}");
    expect(onSelect).toHaveBeenLastCalledWith("si");
    expect(item("si")).toHaveAttribute("aria-selected", "true");
    await userEvent.keyboard("{ArrowDown}{ArrowDown}{ArrowDown} ");
    expect(item("bus_wg")).toHaveFocus();
    expect(onSelect).toHaveBeenLastCalledWith("bus_wg");
    await userEvent.keyboard("{End}");
    expect(item("Boundary")).toHaveFocus();
    await userEvent.keyboard("{ArrowDown}"); // already last
    expect(item("Boundary")).toHaveFocus();
    await userEvent.keyboard("{Home}");
    expect(item("Media")).toHaveFocus();
    await userEvent.keyboard("{ArrowUp}"); // already first
    expect(item("Media")).toHaveFocus();
    expect(onSelect).toHaveBeenCalledTimes(2);
  });

  it("collapses and expands with ←/→ and moves between parent and child", async () => {
    renderWithI18n(<ControlledTree />);
    await userEvent.click(screen.getByRole("button", { name: "before" }));
    await userEvent.tab();
    await userEvent.keyboard("{ArrowDown}{ArrowDown}"); // sio2
    expect(item("sio2")).toHaveFocus();
    await userEvent.keyboard("{ArrowLeft}"); // a leaf: to its parent
    expect(item("Media")).toHaveFocus();
    await userEvent.keyboard("{ArrowLeft}"); // an expanded group: collapse
    expect(item("Media")).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("treeitem", { name: "si" })).not.toBeInTheDocument();
    await userEvent.keyboard("{ArrowDown}"); // skips the hidden children
    expect(item("Structures")).toHaveFocus();
    await userEvent.keyboard("{ArrowUp}{ArrowRight}"); // a collapsed group: expand
    expect(item("Media")).toHaveAttribute("aria-expanded", "true");
    expect(item("Media")).toHaveFocus();
    await userEvent.keyboard("{ArrowRight}"); // an expanded group: first child
    expect(item("si")).toHaveFocus();
    await userEvent.keyboard("{ArrowUp}{Enter}"); // Enter on a group heading toggles it
    expect(item("Media")).toHaveAttribute("aria-expanded", "false");
    await userEvent.keyboard(" ");
    expect(item("Media")).toHaveAttribute("aria-expanded", "true");
  });

  it("selects on click, toggles a group on its heading, hides with the eye", async () => {
    const onSelect = vi.fn();
    const onToggle = vi.fn();
    renderWithI18n(<ControlledTree onSelectSpy={onSelect} onToggleSpy={onToggle} />);
    await userEvent.click(screen.getByText("ring"));
    expect(onSelect).toHaveBeenCalledExactlyOnceWith("ring");
    expect(item("ring")).toHaveFocus();
    await userEvent.click(screen.getByText("Structures"));
    expect(item("Structures")).toHaveAttribute("aria-expanded", "false");
    expect(onSelect).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByText("Structures"));

    // Leaves get an eye; groups do not. sio2 starts hidden and dimmed.
    expect(within(item("si")).getByRole("button", { name: "Hide" })).toBeInTheDocument();
    expect(within(item("sio2")).getByRole("button", { name: "Show" })).toBeInTheDocument();
    expect(item("sio2").firstElementChild).toHaveClass("text-muted");
    expect(screen.getAllByRole("button", { name: /Hide|Show/ })).toHaveLength(5);
    await userEvent.click(within(item("si")).getByRole("button", { name: "Hide" }));
    expect(onToggle).toHaveBeenCalledExactlyOnceWith("si");
    expect(within(item("si")).getByRole("button", { name: "Show" })).toBeInTheDocument();
    expect(item("si").firstElementChild).toHaveClass("text-muted");
    expect(onSelect).toHaveBeenCalledOnce(); // the eye does not select
  });

  it("reaches the eye of the focused row with Tab; Enter on it toggles, not selects", async () => {
    const onSelect = vi.fn();
    const onToggle = vi.fn();
    renderWithI18n(<ControlledTree onSelectSpy={onSelect} onToggleSpy={onToggle} initialSelected="si" />);
    await userEvent.click(screen.getByRole("button", { name: "before" }));
    await userEvent.tab();
    expect(item("si")).toHaveFocus();
    await userEvent.tab();
    expect(within(item("si")).getByRole("button", { name: "Hide" })).toHaveFocus();
    await userEvent.keyboard("{Enter}");
    expect(onToggle).toHaveBeenCalledExactlyOnceWith("si");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("opens the groups around a selection made elsewhere", async () => {
    const { rerender } = renderKeepingState(
      <Tree
        label="Structure"
        nodes={NODES}
        selectedId={null}
        onSelect={vi.fn()}
        hideLabel="Hide"
        showLabel="Show"
      />,
    );
    await userEvent.click(screen.getByText("Structures"));
    expect(screen.queryByRole("treeitem", { name: "ring" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Hide" })).not.toBeInTheDocument(); // no onToggleHidden
    rerender(
      <Tree
        label="Structure"
        nodes={NODES}
        selectedId="ring"
        onSelect={vi.fn()}
        hideLabel="Hide"
        showLabel="Show"
      />,
    );
    expect(item("Structures")).toHaveAttribute("aria-expanded", "true");
    expect(item("ring")).toHaveAttribute("aria-selected", "true");
  });
});

type ResultTab = "fields" | "spectra" | "sparams";

function ControlledTabs({ onChange }: { onChange: (value: ResultTab) => void }) {
  const [tab, setTab] = useState<ResultTab>("fields");
  return (
    <Tabs<ResultTab>
      label="Results"
      value={tab}
      onValueChange={(next) => {
        setTab(next);
        onChange(next);
      }}
      tabs={[
        { value: "fields", label: "Fields" },
        { value: "spectra", label: "Spectra" },
        { value: "sparams", label: "S-parameters", disabled: true, hint: "Needs M2" },
      ]}
    >
      <TabPanel value="fields">Field viewer</TabPanel>
      <TabPanel value="spectra">Spectra chart</TabPanel>
      <TabPanel value="sparams">S-matrix</TabPanel>
    </Tabs>
  );
}

describe("Tabs", () => {
  it("switches panels by click and by arrow key", async () => {
    const onChange = vi.fn();
    renderWithI18n(<ControlledTabs onChange={onChange} />);
    const list = screen.getByRole("tablist", { name: "Results" });
    const fields = within(list).getByRole("tab", { name: "Fields" });
    expect(fields).toHaveAttribute("aria-selected", "true");
    expect(fields).toHaveClass("data-[state=active]:border-accent");
    expect(fields).toHaveAttribute("data-state", "active");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Field viewer");
    await userEvent.click(within(list).getByRole("tab", { name: "Spectra" }));
    expect(onChange).toHaveBeenLastCalledWith("spectra");
    expect(screen.getByRole("tabpanel", { name: "Spectra" })).toHaveTextContent("Spectra chart");
    expect(screen.queryByText("Field viewer")).not.toBeInTheDocument();
    await userEvent.keyboard("{ArrowLeft}");
    expect(fields).toHaveFocus();
    expect(onChange).toHaveBeenLastCalledWith("fields");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Field viewer");
  });

  it("does not open a disabled tab, and explains why", async () => {
    const onChange = vi.fn();
    renderWithI18n(<ControlledTabs onChange={onChange} />);
    const sparams = screen.getByRole("tab", { name: "S-parameters" });
    expect(sparams).toBeDisabled();
    expect(sparams).toHaveAttribute("title", "Needs M2");
    expect(screen.getByRole("tab", { name: "Fields" })).not.toHaveAttribute("title");
    await userEvent.click(sparams);
    expect(onChange).not.toHaveBeenCalled();
    screen.getByRole("tab", { name: "Spectra" }).focus();
    await userEvent.keyboard("{ArrowRight}"); // skips the disabled tab and wraps
    expect(screen.getByRole("tab", { name: "Fields" })).toHaveFocus();
    expect(screen.queryByText("S-matrix")).not.toBeInTheDocument();
  });
});

describe("ProgressBar", () => {
  it("reports 0–100 with its name and detail", () => {
    const { rerender } = renderKeepingState(
      <ProgressBar value={0.4237} label="Run progress" detail="step 18 420 / 26 400" />,
    );
    const bar = screen.getByRole("progressbar", { name: "Run progress" });
    expect(bar).toHaveAttribute("aria-valuenow", "42");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
    expect(bar).toHaveAccessibleDescription("step 18 420 / 26 400");
    expect(bar).toHaveClass("h-2", "border-control");
    expect(bar.firstElementChild).toHaveStyle({ width: "42.37%" });
    expect(bar.firstElementChild).toHaveClass("bg-accent");
    rerender(<ProgressBar value={1.5} label="Run progress" />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
    expect(screen.getByRole("progressbar")).not.toHaveAttribute("aria-describedby");
    rerender(<ProgressBar value={Number.NaN} label="Run progress" />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
    rerender(<ProgressBar value={-1} label="Run progress" />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
  });
});

/** jsdom lays nothing out: give the log a scroll box to follow. */
function fakeScrollBox(element: HTMLElement, content: () => number) {
  let top = 0;
  Object.defineProperty(element, "scrollHeight", { configurable: true, get: content });
  Object.defineProperty(element, "clientHeight", { configurable: true, get: () => 200 });
  Object.defineProperty(element, "scrollTop", {
    configurable: true,
    get: () => top,
    set: (value: number) => {
      top = value;
    },
  });
}

describe("LogView", () => {
  const lines: LogLine[] = [
    { stream: "etalon", line: "grid 420×420×1, dt 3.84e-17 s" },
    { stream: "stdout", line: "building ring" },
    { stream: "stderr", line: "Traceback (most recent call last):" },
  ];

  it("is an unannounced log, coloured by stream", () => {
    renderWithI18n(<LogView label="Log" lines={lines} emptyText="No output yet." />);
    const log = screen.getByRole("log", { name: "Log" });
    expect(log).toHaveAttribute("aria-live", "off");
    expect(log).toHaveAttribute("tabindex", "0");
    expect(log).toHaveAttribute("translate", "no");
    expect(log).toHaveClass("font-mono", "text-dense", "bg-bg");
    expect(screen.getByText("grid 420×420×1, dt 3.84e-17 s")).toHaveClass("text-secondary");
    expect(screen.getByText("building ring")).toHaveClass("text-text");
    expect(screen.getByText("Traceback (most recent call last):")).toHaveClass("text-error");
    expect(screen.queryByText("No output yet.")).not.toBeInTheDocument();
  });

  it("says so when empty", () => {
    renderWithI18n(<LogView label="Log" lines={[]} emptyText="No output yet." />);
    expect(within(screen.getByRole("log")).getByText("No output yet.")).toBeInTheDocument();
  });

  it("keeps the last 2000 lines", () => {
    const many: LogLine[] = Array.from({ length: 2005 }, (_, i) => ({ stream: "stdout", line: `line ${i}` }));
    renderWithI18n(<LogView label="Log" lines={many} emptyText="No output yet." />);
    const log = screen.getByRole("log");
    expect(log.children).toHaveLength(2000);
    expect(log.firstElementChild).toHaveTextContent("line 5");
    expect(log.lastElementChild).toHaveTextContent("line 2004");
    expect(screen.queryByText("line 4")).not.toBeInTheDocument();
  });

  it("follows new lines until the user scrolls up, and again at the bottom", () => {
    let height = 1000;
    const { rerender } = renderKeepingState(<LogView label="Log" lines={lines.slice(0, 1)} emptyText="-" />);
    const log = screen.getByRole("log");
    fakeScrollBox(log, () => height);
    rerender(<LogView label="Log" lines={lines.slice(0, 2)} emptyText="-" />);
    expect(log.scrollTop).toBe(1000);

    log.scrollTop = 300; // the user scrolls up
    fireEvent.scroll(log);
    height = 1200;
    rerender(<LogView label="Log" lines={lines} emptyText="-" />);
    expect(log.scrollTop).toBe(300);

    log.scrollTop = 1000; // back to the bottom (1200 − 200)
    fireEvent.scroll(log);
    height = 1400;
    rerender(<LogView label="Log" lines={[...lines, { stream: "stdout", line: "done" }]} emptyText="-" />);
    expect(log.scrollTop).toBe(1400);
  });

  it("stays put with follow off", () => {
    const { rerender } = renderKeepingState(<LogView label="Log" lines={lines.slice(0, 1)} emptyText="-" follow={false} />);
    const log = screen.getByRole("log");
    fakeScrollBox(log, () => 1000);
    rerender(<LogView label="Log" lines={lines} emptyText="-" follow={false} />);
    expect(log.scrollTop).toBe(0);
  });
});

describe("Inspector", () => {
  it("is a description list: label in secondary, value in mono", () => {
    const { container } = renderWithI18n(
      <Inspector
        rows={[
          { key: "medium", label: "Medium", value: "si" },
          { key: "slab", label: "Slab", value: "±0.110 µm" },
        ]}
      />,
    );
    const terms = container.querySelectorAll("dl > dt");
    const values = container.querySelectorAll("dl > dd");
    expect([...terms].map((t) => t.textContent)).toEqual(["Medium", "Slab"]);
    expect([...values].map((d) => d.textContent)).toEqual(["si", "±0.110 µm"]);
    expect(terms[0]).toHaveClass("text-secondary");
    const value = screen.getByText("±0.110 µm");
    expect(value).toHaveClass("font-mono");
    expect(value).toHaveAttribute("translate", "no");
  });

  it("shows its empty text, or nothing", () => {
    const { container, rerender } = renderWithI18n(<Inspector rows={[]} emptyText="Select an object." />);
    expect(screen.getByText("Select an object.")).toBeInTheDocument();
    expect(container.querySelector("dl")).toBeNull();
    rerender(<Inspector rows={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
