import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useSettings } from "../api/queries";
import { resolveLanguage } from "../i18n";

/** Puts the saved theme and language on <html> and into i18next whenever they change. */
export function useApplySettings(): void {
  const { i18n } = useTranslation();
  const settings = useSettings();
  const theme = settings.data?.theme;
  const language = settings.data?.language;
  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => {
    if (!language) return;
    const resolved = resolveLanguage(language, navigator.language);
    document.documentElement.lang = resolved;
    if (i18n.language !== resolved) void i18n.changeLanguage(resolved);
  }, [language, i18n]);
}
