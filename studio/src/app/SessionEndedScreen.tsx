import { Trans, useTranslation } from "react-i18next";
import { Cmd } from "../components/Cmd";
import { useDocumentTitle } from "./useDocumentTitle";

/** Shown instead of everything once the server answers 401: the token is missing or old. */
export function SessionEndedScreen() {
  const { t } = useTranslation();
  useDocumentTitle(t("session.title"));
  return (
    <div role="alert" className="flex h-full flex-col items-start justify-center gap-3 px-10">
      <div aria-hidden className="spectrum-stripe h-0.5 w-24" />
      <h1 className="text-h1 font-semibold">{t("session.title")}</h1>
      <p className="max-w-[60ch] text-body text-secondary">
        <Trans i18nKey="session.body" components={{ cmd: <Cmd /> }} />
      </p>
    </div>
  );
}
