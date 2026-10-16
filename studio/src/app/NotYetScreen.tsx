import { ArrowLeft } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { useDocumentTitle } from "./useDocumentTitle";

interface NotYetScreenProps {
  screen: "modes" | "validation";
}

/** Mode Solver and Validation arrive in U4; their deep links already resolve. */
export function NotYetScreen({ screen }: NotYetScreenProps) {
  const { t } = useTranslation();
  useDocumentTitle(t(`nav.${screen}`));
  return (
    <section className="h-full overflow-y-auto">
      <div className="border-b border-rule px-4 py-3">
        <h1 className="text-h2 font-semibold">{t(`nav.${screen}`)}</h1>
      </div>
      <EmptyState
        title={t("notYet.title")}
        action={
          <Button asChild icon={<ArrowLeft size={14} aria-hidden />}>
            <Link to="/">{t("simulation.back")}</Link>
          </Button>
        }
      >
        {t(`notYet.${screen}`)}
      </EmptyState>
    </section>
  );
}
