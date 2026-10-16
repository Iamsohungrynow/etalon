import { Trans, useTranslation } from "react-i18next";
import type { SetupWarning } from "../../api/queries";
import { Value } from "../../components/Value";
import { formatBytes } from "../../format/numbers";
import { formatQuantity } from "../../format/units";

interface WarningTextProps {
  warning: SetupWarning;
  /** The object's display name (from the tree), when the warning is about one. */
  objectName?: string;
}

/** A Setup warning in the active language; its numbers stay data (`<v>` → Value). */
export function WarningText({ warning, objectName }: WarningTextProps) {
  const { i18n } = useTranslation();
  const v = <Value />;
  switch (warning.code) {
    case "mesh_coarse":
      return (
        <Trans
          i18nKey="setup.warnings.mesh_coarse"
          values={{
            cells: warning.params.cells_per_wavelength.toFixed(1),
            minimum: warning.params.minimum,
            medium: warning.params.medium ?? "",
            wavelength: formatQuantity(warning.params.wavelength_um, "length", "um", i18n.language),
          }}
          components={{ v }}
        />
      );
    case "pml_thin":
      return (
        <Trans
          i18nKey="setup.warnings.pml_thin"
          values={{
            thickness: formatQuantity(warning.params.thickness_um, "length", "um", i18n.language, 3),
            half: formatQuantity(warning.params.half_wavelength_um, "length", "um", i18n.language, 3),
          }}
          components={{ v }}
        />
      );
    case "near_pml":
      return (
        <Trans
          i18nKey="setup.warnings.near_pml"
          values={{ object: objectName ?? warning.object_id ?? "", cells: warning.params.cells }}
          components={{ v }}
        />
      );
    case "memory_large":
      return (
        <Trans
          i18nKey="setup.warnings.memory_large"
          values={{ memory: formatBytes(warning.params.bytes, i18n.language) }}
          components={{ v }}
        />
      );
    case "unsupported":
      return (
        <Trans
          i18nKey={`setup.warnings.unsupported_${warning.params.feature}`}
          values={{ milestone: warning.params.milestone }}
          components={{ v }}
        />
      );
  }
}
