import type { RouteObject } from "react-router";
import { SettingsScreen } from "../features/settings/SettingsScreen";
import { SimulationScreen } from "../features/simulation/SimulationScreen";
import { WorkspaceScreen } from "../features/workspace/WorkspaceScreen";
import { NotFoundScreen } from "./NotFoundScreen";
import { NotYetScreen } from "./NotYetScreen";
import { Shell } from "./Shell";

/** ui-ux-spec §4. Deep links are stable, so a result can be pasted in a chat. */
export const routes: RouteObject[] = [
  {
    path: "/",
    element: <Shell />,
    children: [
      { index: true, element: <WorkspaceScreen /> },
      { path: "sim/:id/setup", element: <SimulationScreen view="setup" /> },
      { path: "sim/:id/run", element: <SimulationScreen view="run" /> },
      { path: "sim/:id/results", element: <SimulationScreen view="results" /> },
      { path: "modes", element: <NotYetScreen screen="modes" /> },
      { path: "validation", element: <NotYetScreen screen="validation" /> },
      { path: "settings", element: <SettingsScreen /> },
      { path: "*", element: <NotFoundScreen /> },
    ],
  },
];
