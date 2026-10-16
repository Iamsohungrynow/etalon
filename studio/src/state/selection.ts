/**
 * Setup's one selection, shared by the structure tree, the viewport and the inspector
 * (ui-ux-spec §6: selection sync), plus the view-only "hidden" toggles.
 */
import { create } from "zustand";

interface SelectionState {
  /** The simulation the selection belongs to; switching simulations clears it. */
  simulationId: string | null;
  selectedId: string | null;
  hidden: ReadonlySet<string>;
  /** Bumped to ask the viewport to frame the selection (the F key). */
  frameRequest: number;
  open: (simulationId: string) => void;
  select: (id: string | null) => void;
  toggleHidden: (id: string) => void;
  frame: () => void;
}

export const useSelection = create<SelectionState>()((set) => ({
  simulationId: null,
  selectedId: null,
  hidden: new Set<string>(),
  frameRequest: 0,
  open: (simulationId) =>
    set((state) =>
      state.simulationId === simulationId
        ? state
        : { simulationId, selectedId: null, hidden: new Set<string>(), frameRequest: 0 },
    ),
  select: (id) => set({ selectedId: id }),
  toggleHidden: (id) =>
    set((state) => {
      const hidden = new Set(state.hidden);
      if (hidden.has(id)) hidden.delete(id);
      else hidden.add(id);
      return { hidden };
    }),
  frame: () => set((state) => ({ frameRequest: state.frameRequest + 1 })),
}));
