// Chart: the ECharts wrapper's lifecycle and option, and its data-table mode. ECharts itself
// is mocked (jsdom has no canvas), so these check what Studio asks of it.
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  Chart,
  formatSignificant,
  LegendState,
  nearestIndex,
  readoutHtml,
  tableRows,
  type ChartSeries,
} from "./Chart";

const echarts = vi.hoisted(() => {
  let container: HTMLElement | null = null;
  // Like ECharts, dispose empties the container it was given.
  const instance = {
    on: vi.fn(),
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(() => {
      if (container) container.innerHTML = "";
    }),
  };
  const init = vi.fn((element: HTMLElement) => {
    container = element;
    return instance;
  });
  return { instance, init, use: vi.fn() };
});

vi.mock("echarts/core", () => ({ init: echarts.init, use: echarts.use }));
vi.mock("echarts/charts", () => ({ LineChart: {} }));
vi.mock("echarts/components", () => ({
  DataZoomInsideComponent: {},
  GridComponent: {},
  LegendComponent: {},
  MarkLineComponent: {},
  TooltipComponent: {},
}));
vi.mock("echarts/renderers", () => ({ CanvasRenderer: {} }));

// What Chart.tsx registered when it was imported (before any test clears the mocks).
const registered = echarts.use.mock.calls.map((call) => call[0] as unknown[]);

interface SeriesOption {
  name?: string;
  sampling?: string;
  showSymbol?: boolean;
  data: [number, number | null][];
  lineStyle: { type: string; color: string };
  markLine?: { data: { yAxis: number }[] };
}
interface Option {
  animation: boolean;
  series: SeriesOption[];
  yAxis: { type: string; logBase?: number; min?: number; max?: number };
  xAxis: { min: number | string; max: number | string };
  legend: { show: boolean };
  tooltip: { axisPointer: { type: string }; extraCssText: string };
}

function lastOption(): Option {
  const call = echarts.instance.setOption.mock.calls.at(-1) as unknown as [Option, unknown];
  return call[0];
}

const SERIES: ChartSeries[] = [
  { name: "thru", x: [1.5, 1.55, 1.6], y: [0.123456, 0.5, 1] },
  { name: "drop", x: [1.5, 1.55, 1.6], y: [0.0000123456, 0, 2.5e6], dashed: true },
];

const BASE = {
  label: "Spectrum",
  xLabel: "λ (µm)",
  yLabel: "|S|²",
  tableXHeader: "λ (µm)",
};

beforeEach(() => {
  echarts.init.mockClear();
  echarts.instance.setOption.mockClear();
  echarts.instance.dispose.mockClear();
});

describe("Chart", () => {
  it("registers the tree-shaken parts and inits on its labelled container", () => {
    expect(registered).toHaveLength(1);
    expect(registered[0]).toHaveLength(7);
    render(<Chart {...BASE} series={SERIES} />);
    const container = screen.getByRole("img", { name: "Spectrum" });
    expect(echarts.init).toHaveBeenCalledTimes(1);
    expect(echarts.init.mock.calls[0]).toEqual([container, null, { renderer: "canvas" }]);
    expect(echarts.instance.on).toHaveBeenCalledWith("legendselectchanged", expect.any(Function));
  });

  it("sets the series by name, without animation, down-sampled and without symbols", () => {
    render(<Chart {...BASE} series={SERIES} />);
    const option = lastOption();
    expect(echarts.instance.setOption.mock.calls.at(-1)?.[1]).toEqual({ notMerge: true });
    expect(option.animation).toBe(false);
    expect(option.series.map((s) => s.name)).toEqual(["thru", "drop"]);
    expect(option.series.every((s) => s.sampling === "lttb" && s.showSymbol === false)).toBe(true);
    expect(option.series[0]?.data).toEqual([
      [1.5, 0.123456],
      [1.55, 0.5],
      [1.6, 1],
    ]);
    expect(option.series[1]?.lineStyle.type).toBe("dashed");
    expect(option.series[0]?.lineStyle.color).toBe("#E69F00"); // Okabe–Ito orange first
    expect(option.series[1]?.lineStyle.color).toBe("#56B4E9");
    expect(option.legend.show).toBe(true); // two series
    expect(option.tooltip.axisPointer.type).toBe("cross");
    expect(option.tooltip.extraCssText).toContain("box-shadow: none");
    expect(option.xAxis).toMatchObject({ min: "dataMin", max: "dataMax" });
    expect(option.yAxis.type).toBe("value");
  });

  it("maps a log scale and drops the points a log axis cannot show", () => {
    render(<Chart {...BASE} series={SERIES} yScale="log" yDomain={[1e-6, 10]} />);
    const option = lastOption();
    expect(option.yAxis).toMatchObject({ type: "log", logBase: 10, min: 1e-6, max: 10 });
    expect(option.series[1]?.data[1]).toEqual([1.55, null]); // y = 0
  });

  it("draws the reference line and picks colours by index", () => {
    render(
      <Chart
        {...BASE}
        series={[{ name: "energy", x: [0, 1], y: [1, 0.1], colorIndex: 4 }]}
        markY={{ value: 1e-5, label: "threshold" }}
        legend={false}
      />,
    );
    const option = lastOption();
    expect(option.series[0]?.markLine?.data).toEqual([{ yAxis: 1e-5 }]);
    expect(option.series[0]?.lineStyle.color).toBe("#0072B2");
    expect(option.legend.show).toBe(false);
  });

  it("disposes on unmount and re-inits when the theme changes", async () => {
    const { unmount } = render(<Chart {...BASE} series={SERIES} />);
    expect(echarts.init).toHaveBeenCalledTimes(1);
    document.documentElement.dataset.theme = "light";
    await vi.waitFor(() => expect(echarts.init).toHaveBeenCalledTimes(2));
    expect(echarts.instance.dispose).toHaveBeenCalledTimes(1);
    unmount();
    expect(echarts.instance.dispose).toHaveBeenCalledTimes(2);
  });

  it("switches to the table and back without losing either", () => {
    const { rerender } = render(<Chart {...BASE} series={SERIES} />);
    rerender(<Chart {...BASE} series={SERIES} showTable />);
    expect(echarts.instance.dispose).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("table", { name: "Spectrum" })).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(4);
    rerender(<Chart {...BASE} series={SERIES} />);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(echarts.init).toHaveBeenCalledTimes(2);
    expect(echarts.init.mock.calls[1]?.[0]).toBe(screen.getByRole("img", { name: "Spectrum" }));
  });

  it("shows the data as a table instead of the chart", () => {
    render(<Chart {...BASE} series={SERIES} showTable />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(echarts.init).not.toHaveBeenCalled();
    const table = screen.getByRole("table", { name: "Spectrum" });
    const headers = within(table).getAllByRole("columnheader").map((h) => h.textContent);
    expect(headers).toEqual(["λ (µm)", "thru", "drop"]);
    const rows = within(table)
      .getAllByRole("row")
      .slice(1)
      .map((row) => within(row).getAllByRole("cell").map((c) => c.textContent));
    expect(rows).toEqual([
      ["1.5", "0.1235", "1.235e-5"],
      ["1.55", "0.5", "0"],
      ["1.6", "1", "2.5e6"],
    ]);
    // Full precision on hover.
    expect(within(table).getByText("0.1235")).toHaveAttribute("title", "0.123456");
  });
});

describe("Chart helpers", () => {
  it("reads out every series the legend shows at its nearest point", () => {
    const input = { ...BASE, series: SERIES, yScale: "linear" as const, legend: true };
    const legend = new LegendState();
    const html = readoutHtml(1.56, input, ["#E69F00", "#56B4E9"], (n) => legend.shows(n));
    expect(html).toContain("λ (µm)&nbsp;&nbsp;1.56");
    expect(html).toContain("thru<span");
    expect(html).toContain(">0.5</span>");
    expect(html).toContain("drop<span");
    expect(html).toContain("dashed #56B4E9");
    legend.update({ selected: { thru: true, drop: false } });
    const fewer = readoutHtml(1.56, input, ["#E69F00", "#56B4E9"], (n) => legend.shows(n));
    expect(fewer).not.toContain("drop");
    legend.update();
    expect(legend.shows("drop")).toBe(true);
    expect(nearestIndex([1, 2, 3], 2.4)).toBe(1);
    expect(nearestIndex([], 2)).toBe(-1);
  });

  it("escapes series names in the readout", () => {
    const input = {
      ...BASE,
      series: [{ name: "<b>x</b>", x: [0], y: [1] }],
      yScale: "linear" as const,
      legend: false,
    };
    expect(readoutHtml(0, input, ["#000"], () => true)).toContain("&lt;b&gt;x&lt;/b&gt;");
  });

  it("formats 4 significant figures", () => {
    expect(formatSignificant(1.55)).toBe("1.55");
    expect(formatSignificant(1234.56)).toBe("1235");
    expect(formatSignificant(-0.000123456)).toBe("-1.235e-4");
    expect(formatSignificant(1e-5)).toBe("1e-5");
    expect(formatSignificant(0)).toBe("0");
    expect(formatSignificant(Number.NaN)).toBe("NaN");
  });

  it("merges series with different x into one sorted table", () => {
    const rows = tableRows([
      { name: "a", x: [2, 1], y: [20, 10] },
      { name: "b", x: [3, 1], y: [300, 100] },
    ]);
    expect(rows.map((r) => [r.x, ...r.ys])).toEqual([
      [1, 10, 100],
      [2, 20, undefined],
      [3, undefined, 300],
    ]);
  });
});
