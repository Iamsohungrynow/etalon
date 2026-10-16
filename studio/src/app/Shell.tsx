import { useTranslation } from "react-i18next";
import { NavLink, Outlet } from "react-router";
import { cx } from "../components/cx";
import { Value } from "../components/Value";
import { DemoBanner } from "../demo/DemoBanner";
import { DEMO } from "../demo/mode";
import { StatusStrip } from "./StatusStrip";
import { useApplySettings } from "./useApplySettings";

/**
 * Header with navigation, the static spectrum stripe, the screen, the status strip.
 * Mode Solver and Validation join the navigation in U4 (plan-u0 D9).
 */
export function Shell() {
  const { t } = useTranslation();
  useApplySettings();
  const navLink = ({ isActive }: { isActive: boolean }) =>
    cx(
      "motion flex h-full items-center border-b-2 px-1 text-body transition-colors",
      isActive
        ? "border-accent text-text"
        : "border-transparent text-secondary hover:text-text",
    );
  return (
    <div
      className={cx(
        "grid h-full",
        DEMO
          ? "grid-rows-[auto_40px_2px_minmax(0,1fr)_24px]"
          : "grid-rows-[40px_2px_minmax(0,1fr)_24px]",
      )}
    >
      {DEMO ? <DemoBanner /> : null}
      <header className="flex items-center gap-8 bg-surface px-4">
        <Value mono={false} className="text-h3 font-semibold tracking-tight">
          {t("app.brandName")} <span className="font-normal text-secondary">{t("app.brandProduct")}</span>
        </Value>
        <nav aria-label={t("nav.label")} className="flex h-full items-stretch gap-5">
          <NavLink to="/" end className={navLink}>
            {t("nav.workspace")}
          </NavLink>
          <NavLink to="/settings" className={navLink}>
            {t("nav.settings")}
          </NavLink>
        </nav>
      </header>
      <div aria-hidden className="spectrum-stripe" data-testid="spectrum-stripe" />
      <main className="min-h-0 overflow-hidden">
        <Outlet />
      </main>
      <StatusStrip />
    </div>
  );
}
