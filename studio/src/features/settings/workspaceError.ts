import type { TFunction } from "i18next";
import { ServerError } from "../../api/client";

const KNOWN = ["workspace_not_found", "workspace_not_a_directory", "workspace_not_absolute"] as const;
type KnownCode = (typeof KNOWN)[number];

function isKnown(code: string): code is KnownCode {
  return (KNOWN as readonly string[]).includes(code);
}

/** The server's 422 for a workspace folder, as a sentence in the active language. */
export function workspaceErrorMessage(error: unknown, t: TFunction): string {
  if (error instanceof ServerError) {
    const issue = error.issues.find((i) => i.loc[i.loc.length - 1] === "workspace");
    if (issue && isKnown(issue.type)) return t(`settings.workspace.errors.${issue.type}`);
  }
  return t("settings.workspace.errors.other");
}
