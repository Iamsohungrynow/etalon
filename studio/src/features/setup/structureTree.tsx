import type { TFunction } from "i18next";
import type { Preview } from "../../api/queries";
import type { TreeNode } from "../../components/Tree";
import { Value } from "../../components/Value";

const fmt = (value: number) => Number(value.toPrecision(4)).toString();

/** The structure tree (spec §5.2): media, structures, sources, monitors, boundary, grid. */
export function structureTree(preview: Preview, t: TFunction): TreeNode[] {
  const mediumName = (id: string) => preview.media.find((m) => m.id === id)?.name ?? id;
  return [
    {
      id: "group:media",
      label: t("setup.tree.media"),
      selectable: false,
      children: [
        {
          id: "background",
          label: (
            <>
              {t("setup.tree.background")}
              {preview.background.name ? <Value className="text-muted"> {preview.background.name}</Value> : null}
            </>
          ),
          meta: <Value>{fmt(preview.background.n)}</Value>,
        },
        ...preview.media.map((medium) => ({
          id: medium.id,
          label: <Value mono={false}>{medium.name ?? medium.id}</Value>,
          meta: <Value>{fmt(medium.n)}</Value>,
        })),
      ],
    },
    {
      id: "group:structures",
      label: t("setup.tree.structures"),
      selectable: false,
      children: preview.structures.map((structure, i) => ({
        id: structure.id,
        label: structure.name ? <Value mono={false}>{structure.name}</Value> : t("setup.tree.unnamedStructure", { index: i }),
        meta: <Value>{mediumName(structure.medium_id)}</Value>,
      })),
    },
    {
      id: "group:sources",
      label: t("setup.tree.sources"),
      selectable: false,
      children: preview.sources.map((source, i) => ({
        id: source.id,
        label: source.name ? <Value mono={false}>{source.name}</Value> : t("setup.tree.unnamedSource", { index: i }),
        meta: <Value>{source.component}</Value>,
      })),
    },
    {
      id: "group:monitors",
      label: t("setup.tree.monitors"),
      selectable: false,
      children: preview.monitors.map((monitor) => ({
        id: monitor.id,
        label: <Value mono={false}>{monitor.name}</Value>,
        meta: t(`setup.geometry.${monitor.geometry}`),
      })),
    },
    {
      id: "boundary",
      label: t("setup.tree.boundary"),
      meta: (
        <>
          {t("setup.tree.pml")} <Value>{preview.pml.layers}</Value>
        </>
      ),
    },
    {
      id: "grid",
      label: t("setup.tree.grid"),
      meta: preview.grid ? <Value>{`${preview.grid.nx} × ${preview.grid.ny}`}</Value> : undefined,
    },
  ];
}
