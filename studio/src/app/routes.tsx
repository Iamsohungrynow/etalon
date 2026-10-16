import type { RouteObject } from "react-router";
import { SettingsScreen } from "../features/settings/SettingsScreen";
import { WorkspaceScreen } from "../features/workspace/WorkspaceScreen";
import { NotFoundScreen } from "./NotFoundScreen";
import { NotYetScreen } from "./NotYetScreen";
import { Shell } from "./Shell";

/**
 * ui-ux-spec §4. Deep links are stable, so a result can be pasted in a chat.
 *
 * Setup, Run, Results and the kitchen sink load on demand: they carry three.js and
 * ECharts, and the Workspace must still open in under 2 s (plan-u0 P3).
 */
export const routes: RouteObject[] = [
  {
    path: "/",
    element: <Shell />,
    hydrateFallbackElement: null,
    children: [
      { index: true, element: <WorkspaceScreen /> },
      {
        path: "sim/:id/setup",
        lazy: async () => ({ Component: (await import("../features/setup/SetupScreen")).SetupScreen }),
      },
      {
        path: "sim/:id/run",
        lazy: async () => ({ Component: (await import("../features/run/RunScreen")).RunScreen }),
      },
      {
        path: "sim/:id/results",
        lazy: async () => ({
          Component: (await import("../features/results/ResultsScreen")).ResultsScreen,
        }),
      },
      {
        // Every component in every state, for review and the demo; not in the navigation.
        path: "kitchen-sink",
        lazy: async () => ({
          Component: (await import("../features/kitchen/KitchenSinkScreen")).KitchenSinkScreen,
        }),
      },
      { path: "modes", element: <NotYetScreen screen="modes" /> },
      { path: "validation", element: <NotYetScreen screen="validation" /> },
      { path: "settings", element: <SettingsScreen /> },
      { path: "*", element: <NotFoundScreen /> },
    ],
  },
];
