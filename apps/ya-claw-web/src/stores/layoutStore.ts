import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type AppRoute = 'overview' | 'chat' | 'profiles' | 'settings'

export type LayoutState = {
  route: AppRoute
  selectedSessionId: string | null
  selectedRunId: string | null
  selectedProfileName: string | null
  inspectorTab: string
  setRoute: (route: AppRoute) => void
  selectSession: (sessionId: string | null) => void
  selectRun: (runId: string | null) => void
  selectProfile: (profileName: string | null) => void
  setInspectorTab: (tab: string) => void
}

export const useLayoutStore = create<LayoutState>()(
  persist(
    (set) => ({
      route: 'overview',
      selectedSessionId: null,
      selectedRunId: null,
      selectedProfileName: null,
      inspectorTab: 'summary',
      setRoute: (route) => set({ route }),
      selectSession: (selectedSessionId) =>
        set((state) => ({
          selectedSessionId,
          selectedRunId: selectedSessionId ? state.selectedRunId : null,
          route: 'chat',
        })),
      selectRun: (selectedRunId) => set({ selectedRunId, route: 'chat' }),
      selectProfile: (selectedProfileName) =>
        set({ selectedProfileName, route: 'profiles' }),
      setInspectorTab: (inspectorTab) => set({ inspectorTab }),
    }),
    {
      name: 'ya-claw-layout',
      partialize: (state) => ({
        route: state.route,
        selectedSessionId: state.selectedSessionId,
        selectedRunId: state.selectedRunId,
        selectedProfileName: state.selectedProfileName,
        inspectorTab: state.inspectorTab,
      }),
    },
  ),
)
