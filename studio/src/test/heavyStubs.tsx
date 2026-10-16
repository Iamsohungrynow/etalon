/**
 * jsdom has no WebGL and no canvas 2D context: screen tests replace the 3D viewport, the
 * field canvas and the chart with labelled stubs (each has its own tests, and Playwright
 * renders the real thing).
 */
interface Labelled {
  label: string;
}

export function Viewport3DStub({ label }: Labelled) {
  return <div role="img" aria-label={label} data-testid="viewport-stub" />;
}

export function FieldCanvasStub({ label, onHover }: Labelled & { onHover?: (s: { x: number; y: number; value: number } | null) => void }) {
  return (
    <div
      role="img"
      aria-label={label}
      data-testid="field-stub"
      onMouseMove={() => onHover?.({ x: 0, y: 0, value: 12.08 })}
    />
  );
}

export function ChartStub({ label, series, showTable }: Labelled & { series: { name: string; x: number[] }[]; showTable?: boolean }) {
  return showTable ? (
    <table aria-label={label}>
      <tbody>
        {series.map((s) => (
          <tr key={s.name}>
            <td>{s.name}</td>
            <td>{s.x.length}</td>
          </tr>
        ))}
      </tbody>
    </table>
  ) : (
    <div role="img" aria-label={label} data-testid="chart-stub" data-series={series.map((s) => s.name).join("|")} />
  );
}
