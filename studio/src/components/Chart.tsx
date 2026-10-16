import { LineChart, type LineSeriesOption } from "echarts/charts";
import {
  DataZoomInsideComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  type DataZoomComponentOption,
  type GridComponentOption,
  type LegendComponentOption,
  type MarkLineComponentOption,
  type TooltipComponentOption,
} from "echarts/components";
// `use` renamed: it is ECharts' registration, not React's use() hook.
import { init, use as registerECharts, type ComposeOption, type EChartsType } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useMemo, useRef, useState } from "react";
import { isDarkTokens, readTokens, seriesColor, token, useThemeVersion } from "../charts/theme";
import { cx } from "./cx";
import { Table, type Column } from "./Table";
import { Value } from "./Value";

// Tree-shaken ECharts: line series on a cartesian grid, axis tooltip with a crosshair,
// legend, one threshold line, wheel/drag zoom inside the plot (no slider), canvas only.
registerECharts([
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  DataZoomInsideComponent,
  CanvasRenderer,
]);

type ChartOption = ComposeOption<
  | LineSeriesOption
  | GridComponentOption
  | TooltipComponentOption
  | LegendComponentOption
  | MarkLineComponentOption
  | DataZoomComponentOption
>;

export interface ChartSeries {
  /** Legend, tooltip and table-column name (data, e.g. a monitor name; not translated). */
  name: string;
  x: number[];
  y: number[];
  /** Dashed line, e.g. the second run of a comparison. */
  dashed?: boolean;
  /** Okabe–Ito colour index; defaults to the series' position. */
  colorIndex?: number;
}

export interface ChartProps {
  /** Accessible name of the chart (and of its data table). */
  label: string;
  series: readonly ChartSeries[];
  /** Axis titles with their units, e.g. "λ (µm)". */
  xLabel: string;
  yLabel: string;
  yScale?: "linear" | "log";
  xDomain?: [number, number];
  yDomain?: [number, number];
  /** A horizontal reference line, e.g. a shutoff threshold. */
  markY?: { value: number; label: string };
  /** Show the data as a table instead of the chart (spec §7: charts have a table toggle). */
  showTable?: boolean;
  /** Header of the table's x column, e.g. "λ (µm)". */
  tableXHeader: string;
  /**
   * Height in px of the chart (or of the table). Without it the chart fills its parent's
   * height (give the parent one), and is never shorter than 160 px.
   */
  height?: number;
  /** Show the legend; by default only when there is more than one series. */
  legend?: boolean;
  className?: string;
}

const MONO = '"JetBrains Mono Variable", ui-monospace, Menlo, Consolas, monospace';
const FONT_SIZE = 11;
const MIN_HEIGHT = 160;

/** 4 significant figures (spec §6); exponent form below 1e-3 and from 1e6. */
export function formatSignificant(value: number): string {
  if (Number.isNaN(value)) return "NaN";
  if (!Number.isFinite(value)) return value > 0 ? "∞" : "-∞";
  if (value === 0) return "0";
  const magnitude = Math.abs(value);
  if (magnitude < 1e-3 || magnitude >= 1e6) {
    const [mantissa = "", exponent = ""] = value.toExponential(3).split("e");
    const trimmed = mantissa.includes(".") ? mantissa.replace(/\.?0+$/, "") : mantissa;
    return `${trimmed}e${exponent.replace("+", "")}`;
  }
  return String(Number(value.toPrecision(4)));
}

function escapeHtml(text: string): string {
  return text.replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] ?? c,
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** The crosshair's x: the axis value ECharts passes to an axis-trigger tooltip. */
function axisValueOf(params: unknown): number | undefined {
  for (const item of Array.isArray(params) ? params : [params]) {
    if (isRecord(item) && typeof item.axisValue === "number") return item.axisValue;
  }
  return undefined;
}

/** Index of the x nearest to `x` (-1 for none). */
export function nearestIndex(xs: readonly number[], x: number): number {
  let best = -1;
  let distance = Infinity;
  for (let i = 0; i < xs.length; i++) {
    const d = Math.abs((xs[i] ?? Number.NaN) - x);
    if (d < distance) {
      distance = d;
      best = i;
    }
  }
  return best;
}

/**
 * The crosshair readout: x, then every series the legend shows at its nearest point, from
 * the full-resolution data. (ECharts' own list holds only the series whose down-sampled
 * point is nearest, which drops the others when LTTB keeps different x per series.)
 */
export function readoutHtml(
  x: number,
  input: ChartOptionInput,
  colors: readonly string[],
  shows: (name: string) => boolean,
): string {
  const lines = [`${escapeHtml(input.xLabel)}&nbsp;&nbsp;${formatSignificant(x)}`];
  input.series.forEach((s, i) => {
    const j = nearestIndex(s.x, x);
    if (j < 0 || !shows(s.name)) return;
    const y = s.y[j];
    const line = `border-top:2px ${s.dashed ? "dashed" : "solid"} ${colors[i] ?? ""}`;
    const swatch = `<span style="display:inline-block;width:12px;margin-right:6px;vertical-align:middle;${line}"></span>`;
    const value = typeof y === "number" ? formatSignificant(y) : "–";
    lines.push(
      `${swatch}${escapeHtml(s.name)}<span style="float:right;margin-left:16px">${value}</span>`,
    );
  });
  return lines.join("<br/>");
}

/** Which series the legend has switched off, for the readout to skip. */
export class LegendState {
  private readonly off = new Set<string>();

  /** From ECharts' `legendselectchanged` event; no argument resets to all shown. */
  update(event?: unknown) {
    this.off.clear();
    const selected = isRecord(event) && isRecord(event.selected) ? event.selected : {};
    for (const [name, on] of Object.entries(selected)) if (on === false) this.off.add(name);
  }

  shows(name: string): boolean {
    return !this.off.has(name);
  }
}

/** [x, y] pairs; a point a log axis cannot show (y ≤ 0, NaN, ±∞) becomes a gap. */
function pairs(series: ChartSeries, log: boolean): [number, number | null][] {
  const n = Math.min(series.x.length, series.y.length);
  const data = new Array<[number, number | null]>(n);
  for (let i = 0; i < n; i++) {
    const y = series.y[i] ?? Number.NaN;
    data[i] = [series.x[i] ?? Number.NaN, Number.isFinite(y) && (!log || y > 0) ? y : null];
  }
  return data;
}

export interface ChartOptionInput {
  series: readonly ChartSeries[];
  xLabel: string;
  yLabel: string;
  yScale: "linear" | "log";
  xDomain?: [number, number];
  yDomain?: [number, number];
  markY?: { value: number; label: string };
  legend: boolean;
  /** Whether the legend shows a series (read at hover time); all by default. */
  shows?: (name: string) => boolean;
}

/** The ECharts option, themed from the resolved `--et-*` tokens. */
export function chartOption(input: ChartOptionInput, tokens: Record<string, string>): ChartOption {
  const dark = isDarkTokens(tokens);
  const rule = token(tokens, "rule");
  const ruleSubtle = token(tokens, "rule-subtle");
  const muted = token(tokens, "muted");
  const text = token(tokens, "text");
  const log = input.yScale === "log";
  const label = { color: muted, fontFamily: MONO, fontSize: FONT_SIZE };

  const markLine: MarkLineComponentOption | undefined = input.markY && {
    silent: true,
    animation: false,
    symbol: ["none", "none"],
    lineStyle: { color: muted, type: "dashed", width: 1 },
    label: { ...label, position: "insideEndTop", formatter: () => input.markY?.label ?? "" },
    data: [{ yAxis: input.markY.value }],
  };

  const colors = input.series.map((s, i) => seriesColor(s.colorIndex ?? i, dark));
  const shows = input.shows ?? (() => true);
  const series: LineSeriesOption[] = input.series.map((s, i) => {
    const color = colors[i];
    return {
      type: "line",
      name: s.name,
      data: pairs(s, log),
      showSymbol: false,
      symbol: "none",
      sampling: "lttb",
      connectNulls: false,
      animation: false,
      color,
      lineStyle: { color, width: 1.5, type: s.dashed ? "dashed" : "solid" },
      emphasis: { disabled: true },
      ...(i === 0 && markLine ? { markLine } : {}),
    };
  });
  // A threshold with no data yet still shows (the Run chart before its first point).
  if (series.length === 0 && markLine) series.push({ type: "line", data: [], markLine });

  return {
    animation: false,
    backgroundColor: "transparent",
    textStyle: { fontFamily: MONO, fontSize: FONT_SIZE, color: muted },
    grid: {
      left: 8,
      right: 16,
      top: input.legend ? 32 : 16,
      bottom: 8,
      outerBoundsMode: "same",
      outerBoundsContain: "all",
    },
    legend: {
      show: input.legend,
      top: 0,
      right: 8,
      itemWidth: 18,
      itemHeight: 8,
      textStyle: label,
      inactiveColor: rule,
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: token(tokens, "surface"),
      borderColor: rule,
      borderWidth: 1,
      padding: [4, 8],
      transitionDuration: 0,
      textStyle: { color: text, fontFamily: MONO, fontSize: FONT_SIZE },
      extraCssText: "box-shadow: none; border-radius: 0;",
      axisPointer: {
        type: "cross",
        animation: false,
        lineStyle: { color: muted, width: 1 },
        crossStyle: { color: muted, width: 1 },
        label: {
          backgroundColor: token(tokens, "raised"),
          color: text,
          fontFamily: MONO,
          fontSize: FONT_SIZE,
          formatter: (p: { value: unknown }) =>
            typeof p.value === "number" ? formatSignificant(p.value) : String(p.value),
        },
      },
      formatter: (params: unknown) => {
        const x = axisValueOf(params);
        return x === undefined ? "" : readoutHtml(x, input, colors, shows);
      },
    },
    dataZoom: [{ type: "inside", xAxisIndex: 0, filterMode: "none" }],
    xAxis: {
      type: "value",
      name: input.xLabel,
      nameLocation: "middle",
      nameGap: 24,
      nameTextStyle: label,
      min: input.xDomain?.[0] ?? "dataMin",
      max: input.xDomain?.[1] ?? "dataMax",
      axisLine: { lineStyle: { color: rule } },
      axisTick: { lineStyle: { color: rule } },
      axisLabel: { ...label, formatter: (v: number) => formatSignificant(v) },
      splitLine: { lineStyle: { color: ruleSubtle } },
    },
    yAxis: {
      type: log ? "log" : "value",
      ...(log ? { logBase: 10 } : {}),
      name: input.yLabel,
      nameLocation: "middle",
      nameGap: 40,
      nameTextStyle: label,
      ...(input.yDomain ? { min: input.yDomain[0], max: input.yDomain[1] } : {}),
      axisLine: { show: true, lineStyle: { color: rule } },
      axisTick: { show: true, lineStyle: { color: rule } },
      axisLabel: { ...label, formatter: (v: number) => formatSignificant(v) },
      splitLine: { lineStyle: { color: ruleSubtle } },
    },
    series,
  };
}

interface TableRow {
  key: string;
  x: number;
  ys: (number | undefined)[];
}

function sameX(a: readonly number[], b: readonly number[]): boolean {
  return a === b || (a.length === b.length && a.every((v, i) => v === b[i]));
}

/** One row per x: the series' own x when they share it, else the sorted union of all x. */
export function tableRows(series: readonly ChartSeries[]): TableRow[] {
  const first = series[0];
  if (!first) return [];
  if (series.every((s) => sameX(s.x, first.x))) {
    return first.x.map((x, i) => ({ key: String(i), x, ys: series.map((s) => s.y[i]) }));
  }
  const byX = new Map<number, (number | undefined)[]>();
  series.forEach((s, j) => {
    s.x.forEach((x, i) => {
      const row = byX.get(x) ?? new Array<number | undefined>(series.length).fill(undefined);
      row[j] = s.y[i];
      byX.set(x, row);
    });
  });
  return [...byX.entries()]
    .sort(([a], [b]) => a - b)
    .map(([x, ys], i) => ({ key: String(i), x, ys }));
}

function numberCell(value: number | undefined) {
  if (value === undefined) return null;
  return <Value title={String(value)}>{formatSignificant(value)}</Value>;
}

/**
 * A line chart (ECharts, canvas) themed by the design tokens, or its data as a table.
 * Copes with 10 000 points per series (LTTB down-sampling, no symbols). Memoise `series`
 * in the caller: a new array re-renders the chart.
 */
export function Chart({
  label,
  series,
  xLabel,
  yLabel,
  yScale = "linear",
  xDomain,
  yDomain,
  markY,
  showTable = false,
  tableXHeader,
  height,
  legend,
  className,
}: ChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<EChartsType | null>(null);
  const [legendState] = useState(() => new LegendState());
  const themeVersion = useThemeVersion();
  const showLegend = legend ?? series.length > 1;
  const xMin = xDomain?.[0];
  const xMax = xDomain?.[1];
  const yMin = yDomain?.[0];
  const yMax = yDomain?.[1];
  const markValue = markY?.value;
  const markLabel = markY?.label;

  const option = useMemo(
    () =>
      chartOption(
        {
          series,
          xLabel,
          yLabel,
          yScale,
          xDomain: xMin !== undefined && xMax !== undefined ? [xMin, xMax] : undefined,
          yDomain: yMin !== undefined && yMax !== undefined ? [yMin, yMax] : undefined,
          markY:
            markValue !== undefined && markLabel !== undefined
              ? { value: markValue, label: markLabel }
              : undefined,
          legend: showLegend,
          shows: (name) => legendState.shows(name),
        },
        // Re-read on every theme change: themeVersion is the dependency that says so.
        readTokensAt(themeVersion),
      ),
    [
      series,
      xLabel,
      yLabel,
      yScale,
      xMin,
      xMax,
      yMin,
      yMax,
      markValue,
      markLabel,
      showLegend,
      legendState,
      themeVersion,
    ],
  );

  // One ECharts instance per theme: re-created when the theme changes, disposed on unmount.
  useEffect(() => {
    const container = containerRef.current;
    if (showTable || !container) return;
    const chart = init(container, null, { renderer: "canvas" });
    chart.on("legendselectchanged", (event: unknown) => legendState.update(event));
    chartRef.current = chart;
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(container);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, [showTable, themeVersion, legendState]);

  // notMerge resets the legend to all shown, so the readout's view of it resets too.
  useEffect(() => {
    legendState.update();
    chartRef.current?.setOption(option, { notMerge: true });
  }, [option, showTable, legendState]);

  const rows = useMemo(() => (showTable ? tableRows(series) : []), [series, showTable]);
  const columns = useMemo<Column<TableRow>[]>(
    () => [
      {
        id: "x",
        // As given: the micro-label's uppercase would turn "µm" into "ΜM".
        header: <span className="normal-case">{tableXHeader}</span>,
        width: "minmax(0, 1fr)",
        align: "end",
        cell: (row) => numberCell(row.x),
      },
      ...series.map(
        (s, j): Column<TableRow> => ({
          id: `s${j}`,
          header: (
            <Value mono={false} className="normal-case">
              {s.name}
            </Value>
          ),
          width: "minmax(0, 1fr)",
          align: "end",
          cell: (row) => numberCell(row.ys[j]),
        }),
      ),
    ],
    [series, tableXHeader],
  );

  const box = height === undefined ? { height: "100%", minHeight: MIN_HEIGHT } : { height };
  // Distinct keys: ECharts empties its container on dispose, which runs after React has
  // committed, so the table must never be rendered into the chart's old element.
  if (showTable) {
    return (
      <div key="table" className={cx("flex flex-col", className)} style={box}>
        <Table label={label} columns={columns} rows={rows} rowKey={(row) => row.key} />
      </div>
    );
  }
  return (
    <div
      key="chart"
      ref={containerRef}
      role="img"
      aria-label={label}
      className={cx("w-full cursor-crosshair", className)}
      style={box}
    />
  );
}

/** readTokens(), keyed on the theme version so a memo re-reads it when the theme changes. */
function readTokensAt(themeVersion: number): Record<string, string> {
  void themeVersion;
  return readTokens();
}
