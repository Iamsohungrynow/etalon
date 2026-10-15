// V4: roles, names, keyboard and states of the design-system components.
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Search } from "lucide-react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { renderWithI18n } from "../test/renderApp";
import { Banner } from "./Banner";
import { Button } from "./Button";
import { EmptyState } from "./EmptyState";
import { ErrorPanel } from "./ErrorPanel";
import { IconButton } from "./IconButton";
import { Segmented } from "./Segmented";
import { Select } from "./Select";
import { Skeleton } from "./Skeleton";
import { Table } from "./Table";
import { TextField } from "./TextField";
import { Toggle } from "./Toggle";
import { Value } from "./Value";

describe("Button and IconButton", () => {
  it("is a type=button that clicks, and stops when disabled", async () => {
    const onClick = vi.fn();
    const { rerender } = renderWithI18n(<Button onClick={onClick}>Apply</Button>);
    const button = screen.getByRole("button", { name: "Apply" });
    expect(button).toHaveAttribute("type", "button");
    await userEvent.click(button);
    button.focus();
    await userEvent.keyboard("{Enter}");
    expect(onClick).toHaveBeenCalledTimes(2);
    rerender(
      <Button onClick={onClick} disabled>
        Apply
      </Button>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(onClick).toHaveBeenCalledTimes(2);
  });

  it("styles a link with asChild", () => {
    renderWithI18n(
      <Button asChild variant="primary">
        <a href="/settings">Settings</a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Settings" });
    expect(link).toHaveClass("bg-accent");
    expect(link).not.toHaveAttribute("type");
  });

  it("names an icon-only button by its label", () => {
    renderWithI18n(<IconButton label="Rescan" icon={<Search />} />);
    const button = screen.getByRole("button", { name: "Rescan" });
    expect(button).toHaveAttribute("title", "Rescan");
  });
});

describe("TextField", () => {
  it("labels the input, describes help and errors", async () => {
    const { rerender } = renderWithI18n(<TextField label="Folder path" help="Absolute path" />);
    const input = screen.getByRole("textbox", { name: "Folder path" });
    expect(input).toHaveAccessibleDescription("Absolute path");
    expect(input).not.toHaveAttribute("aria-invalid");
    rerender(<TextField label="Folder path" error="This folder does not exist." />);
    expect(screen.getByRole("textbox", { name: "Folder path" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("textbox")).toHaveAccessibleDescription("This folder does not exist.");
    await userEvent.type(screen.getByRole("textbox"), "C:\\x");
    expect(screen.getByRole("textbox")).toHaveValue("C:\\x");
  });

  it("keeps a hidden label for screen readers", () => {
    renderWithI18n(<TextField label="Filter" hideLabel />);
    expect(screen.getByRole("textbox", { name: "Filter" })).toBeInTheDocument();
    expect(screen.getByText("Filter")).toHaveClass("sr-only");
  });
});

describe("Toggle", () => {
  function Controlled({ onChange }: { onChange: (v: boolean) => void }) {
    const [on, setOn] = useState(false);
    return (
      <Toggle
        label="Live field snapshots"
        help="Costs a little speed."
        checked={on}
        onCheckedChange={(v) => {
          setOn(v);
          onChange(v);
        }}
      />
    );
  }

  it("is a switch toggled by click, label and Space", async () => {
    const onChange = vi.fn();
    renderWithI18n(<Controlled onChange={onChange} />);
    const toggle = screen.getByRole("switch", { name: "Live field snapshots" });
    expect(toggle).toHaveAccessibleDescription("Costs a little speed.");
    await userEvent.click(toggle);
    expect(toggle).toBeChecked();
    await userEvent.click(screen.getByText("Live field snapshots"));
    expect(toggle).not.toBeChecked();
    toggle.focus();
    await userEvent.keyboard(" ");
    expect(onChange.mock.calls).toEqual([[true], [false], [true]]);
  });
});

describe("Segmented", () => {
  const options = [
    { value: "dark", label: "Dark" },
    { value: "light", label: "Light" },
    { value: "system", label: "System" },
  ] as const;

  it("moves with arrow keys, picks with Space, never reports an empty value", async () => {
    const onValueChange = vi.fn();
    renderWithI18n(
      <Segmented label="Theme" value="dark" options={options} onValueChange={onValueChange} />,
    );
    const group = screen.getByRole("radiogroup", { name: "Theme" });
    const dark = within(group).getByRole("radio", { name: "Dark" });
    expect(dark).toHaveAttribute("aria-checked", "true");
    await userEvent.click(dark); // the active item again: Radix would report ""
    expect(onValueChange).not.toHaveBeenCalled();
    dark.focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(within(group).getByRole("radio", { name: "Light" })).toHaveFocus();
    await userEvent.keyboard(" ");
    expect(onValueChange).toHaveBeenCalledWith("light");
  });
});

describe("Select", () => {
  it("opens from the keyboard, picks an option, closes on Escape", async () => {
    const onValueChange = vi.fn();
    renderWithI18n(
      <Select
        label="Backend"
        value="auto"
        onValueChange={onValueChange}
        options={[
          { value: "auto", label: "Auto" },
          { value: "cpu", label: "CPU" },
        ]}
      />,
    );
    const trigger = screen.getByRole("combobox", { name: "Backend" });
    expect(trigger).toHaveTextContent("Auto");
    await userEvent.click(trigger);
    await userEvent.click(await screen.findByRole("option", { name: "CPU" }));
    expect(onValueChange).toHaveBeenCalledWith("cpu");
    trigger.focus();
    await userEvent.keyboard("{Enter}");
    expect(await screen.findByRole("listbox")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});

describe("Table", () => {
  const rows = Array.from({ length: 50 }, (_, i) => ({ id: `r${i}`, name: `script_${i}.py` }));

  it("is a table with headers and only the visible rows in the DOM", () => {
    renderWithI18n(
      <Table
        label="Simulations"
        rows={rows}
        rowKey={(row) => row.id}
        columns={[{ id: "name", header: "Name", width: "1fr", cell: (row) => row.name }]}
      />,
    );
    const table = screen.getByRole("table", { name: "Simulations" });
    expect(table).toHaveAttribute("aria-rowcount", "51");
    expect(within(table).getByRole("columnheader", { name: "Name" })).toBeInTheDocument();
    const rendered = within(table).getAllByRole("row").slice(1);
    expect(rendered.length).toBeGreaterThan(5);
    expect(rendered.length).toBeLessThan(50);
    expect(rendered[0]).toHaveAttribute("aria-rowindex", "2");
    expect(within(table).getByText("script_0.py")).toBeInTheDocument();
  });
});

describe("Banner, EmptyState, ErrorPanel, Skeleton, Value", () => {
  it("Banner is a status line with an action", () => {
    renderWithI18n(<Banner action={<a href="/settings">Settings</a>}>No CUDA device found.</Banner>);
    expect(screen.getByRole("status")).toHaveTextContent("No CUDA device found.");
    expect(screen.getByRole("link", { name: "Settings" })).toBeInTheDocument();
  });

  it("EmptyState has a heading, text and an action", () => {
    renderWithI18n(
      <EmptyState title="No scripts" action={<button type="button">Choose</button>}>
        Add one.
      </EmptyState>,
    );
    expect(screen.getByRole("heading", { name: "No scripts" })).toBeInTheDocument();
    expect(screen.getByText("Add one.")).toBeInTheDocument();
  });

  it("ErrorPanel is an alert with detail as data and a translated Retry", async () => {
    const onRetry = vi.fn();
    renderWithI18n(<ErrorPanel title="Failed" detail="/data/gone" onRetry={onRetry} />, "zh-CN");
    expect(screen.getByRole("alert")).toHaveTextContent("Failed");
    expect(screen.getByText("/data/gone")).toHaveAttribute("translate", "no");
    await userEvent.click(screen.getByRole("button", { name: "重试" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("Skeleton is hidden from assistive tech; Value is not translated", () => {
    const { container } = renderWithI18n(
      <>
        <Skeleton />
        <Value title="42300000">42.3 M</Value>
      </>,
    );
    expect(container.querySelector("[aria-hidden]")).not.toBeNull();
    const value = screen.getByText("42.3 M");
    expect(value).toHaveAttribute("translate", "no");
    expect(value).toHaveClass("font-mono");
  });
});
