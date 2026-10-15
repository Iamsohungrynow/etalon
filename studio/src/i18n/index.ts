/**
 * i18next with both catalogues bundled (no HTTP backend: nothing is fetched at runtime).
 * Keys are namespaced by feature. Data (file names, paths, numbers with units, device
 * names) is never translated: it is rendered through <Value translate="no">.
 */
import i18next, { type i18n } from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";
import zhCN from "./zh-CN.json";

export const resources = {
  en: { translation: en },
  "zh-CN": { translation: zhCN },
} as const;

export type Language = keyof typeof resources;
export type LanguageSetting = Language | "system";
export const LANGUAGES: readonly Language[] = ["en", "zh-CN"];

/** Each language named in itself, as language pickers do; deliberately not translated. */
export const LANGUAGE_NAMES: Record<Language, string> = { en: "English", "zh-CN": "简体中文" };

declare module "i18next" {
  interface CustomTypeOptions {
    resources: { translation: typeof en };
  }
}

/** "system" → the browser's language: Chinese of any region → zh-CN, else English. */
export function resolveLanguage(setting: LanguageSetting, browserLanguage: string): Language {
  if (setting !== "system") return setting;
  return browserLanguage.toLowerCase().startsWith("zh") ? "zh-CN" : "en";
}

/** The language the server already put on <html lang>, so the first paint needs no switch. */
export function initialLanguage(doc: Document = document): Language {
  return doc.documentElement.lang === "zh-CN" ? "zh-CN" : "en";
}

export function createI18n(language: Language): i18n {
  const instance = i18next.createInstance();
  void instance.use(initReactI18next).init({
    resources,
    lng: language,
    fallbackLng: "en",
    supportedLngs: [...LANGUAGES],
    interpolation: { escapeValue: false }, // React escapes already
    returnNull: false,
    initAsync: false,
  });
  return instance;
}
