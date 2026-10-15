import { ArrowLeft } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { Value } from "../components/Value";
import { useDocumentTitle } from "./useDocumentTitle";

export function NotFoundScreen() {
  const { t } = useTranslation();
  const location = useLocation();
  useDocumentTitle(t("notFound.title"));
  return (
    <section className="h-full overflow-y-auto">
      <EmptyState
        title={t("notFound.title")}
        action={
          <Button asChild icon={<ArrowLeft size={14} aria-hidden />}>
            <Link to="/">{t("simulation.back")}</Link>
          </Button>
        }
      >
        <p>{t("notFound.body")}</p>
        <Value className="text-dense text-muted">{location.pathname}</Value>
      </EmptyState>
    </section>
  );
}
