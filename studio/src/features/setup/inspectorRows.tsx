import type { TFunction } from "i18next";
import type { ReactNode } from "react";
import type { Preview } from "../../api/queries";
import type { InspectorRow } from "../../components/Inspector";
import { Value } from "../../components/Value";
import { formatQuantity, unitSymbol, type Unit } from "../../format/units";

type Vec = readonly number[];

/** "−2.1, 0.4 µm" in the chosen length unit; the z coordinate only for 3D. */
function lengths(values: Vec, unit: Unit, locale: string): string {
  const numbers = values.map((v) => formatQuantity(v, "length", unit, locale).split(" ")[0]);
  return `${numbers.join(", ")} ${unitSymbol(unit)}`;
}

function one(value: number, quantity: "length" | "time", unit: Unit, locale: string): string {
  return formatQuantity(value, quantity, unit, locale);
}

/** Read-only properties of the selected object, with units (spec §5.2 Inspector). */
export function inspectorRows(
  preview: Preview,
  id: string | null,
  t: TFunction,
  lengthUnit: Unit,
  locale: string,
): InspectorRow[] {
  const v = (text: ReactNode) => <Value>{text}</Value>;
  const plane = (xyz: Vec) => (preview.is_2d ? xyz.slice(0, 2) : xyz);
  const row = (key: string, value: ReactNode): InspectorRow => ({
    key,
    label: t(`setup.inspector.${key}` as "setup.inspector.center"),
    value,
  });

  if (id === "background") {
    const n = preview.background.n;
    return [
      row("medium", preview.background.name ? v(preview.background.name) : t("setup.tree.background")),
      row("index", v(n.toPrecision(5))),
      row("permittivity", v((n * n).toPrecision(5))),
    ];
  }
  const medium = preview.media.find((m) => m.id === id);
  if (medium) {
    return [
      row("medium", v(medium.name ?? medium.id)),
      row("index", v(medium.n.toPrecision(5))),
      row("permittivity", v((medium.n * medium.n).toPrecision(5))),
      row("usedBy", v(preview.structures.filter((s) => s.medium_id === medium.id).length)),
    ];
  }
  const structure = preview.structures.find((s) => s.id === id);
  if (structure) {
    const m = preview.media.find((x) => x.id === structure.medium_id);
    return [
      row("kind", v(structure.kind)),
      row("medium", v(m?.name ?? structure.medium_id)),
      row("index", v(m ? m.n.toPrecision(5) : "—")),
      row("center", v(lengths(plane(structure.center), lengthUnit, locale))),
      row("size", v(lengths(plane(structure.size), lengthUnit, locale))),
    ];
  }
  const source = preview.sources.find((s) => s.id === id);
  if (source) {
    return [
      row("kind", v(source.kind)),
      row("component", v(source.component)),
      row("center", v(lengths(plane(source.center), lengthUnit, locale))),
      row("wavelength", v(one(source.wavelength_um, "length", lengthUnit, locale))),
      row("bandwidth", v(one(source.bandwidth_um, "length", lengthUnit, locale))),
    ];
  }
  const monitor = preview.monitors.find((m) => m.id === id);
  if (monitor) {
    return [
      row("geometry", t(`setup.geometry.${monitor.geometry}`)),
      row("center", v(lengths(plane(monitor.center), lengthUnit, locale))),
      row("size", v(lengths(plane(monitor.size), lengthUnit, locale))),
      row("wavelengths", v(lengths(monitor.wavelengths_um, lengthUnit, locale))),
      row("components", v(monitor.components.join(", "))),
    ];
  }
  if (id === "boundary") {
    return [
      row("kind", v("CPML")),
      row("layers", v(preview.pml.layers)),
      row("thickness", v(lengths(plane(preview.pml.thickness), lengthUnit, locale))),
    ];
  }
  if (id === "grid" && preview.grid) {
    const g = preview.grid;
    return [
      row("cell", v(lengths([g.dx, g.dy], lengthUnit, locale))),
      row("cells", v(`${g.nx} × ${g.ny}`)),
      row("regionCells", v(`${g.region_cells[0]} × ${g.region_cells[1]}`)),
      row("dt", v(one(g.dt_s, "time", "fs", locale))),
      row("courant", v(g.courant)),
      row("steps", v(g.steps)),
    ];
  }
  return [];
}
