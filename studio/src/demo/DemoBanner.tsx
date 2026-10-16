import { Trans } from "react-i18next";
import { Banner } from "../components/Banner";
import { Cmd } from "../components/Cmd";

/** Above everything in the demo build: these are recorded results, not a running Studio. */
export function DemoBanner() {
  return (
    <Banner tone="info">
      <span data-testid="demo-banner">
        <Trans i18nKey="demo.banner" components={{ cmd: <Cmd /> }} />
      </span>
    </Banner>
  );
}
