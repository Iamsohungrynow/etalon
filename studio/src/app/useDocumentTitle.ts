import { useEffect } from "react";
import { useTranslation } from "react-i18next";

/** "Workspace · etalon Studio", in the active language. */
export function useDocumentTitle(screen: string): void {
  const { t } = useTranslation();
  const title = t("app.documentTitle", { screen });
  useEffect(() => {
    document.title = title;
  }, [title]);
}
