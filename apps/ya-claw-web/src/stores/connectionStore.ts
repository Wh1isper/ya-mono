import { create } from 'zustand'
import { persist } from 'zustand/middleware'

function getDefaultBaseUrl() {
  if (typeof window !== 'undefined') {
    return window.location.origin
  }
  return import.meta.env.VITE_CLAW_BASE_URL ?? 'http://127.0.0.1:9042'
}

function normalizeBaseUrl(baseUrl: string) {
  return baseUrl.trim().replace(/\/$/, '')
}

const defaultBaseUrl = getDefaultBaseUrl()

export type ConnectionState = {
  baseUrl: string
  apiToken: string
  setBaseUrl: (baseUrl: string) => void
  setApiToken: (apiToken: string) => void
  setConnection: (connection: { baseUrl: string; apiToken: string }) => void
  logout: () => void
}

export const useConnectionStore = create<ConnectionState>()(
  persist(
    (set) => ({
      baseUrl: defaultBaseUrl,
      apiToken: import.meta.env.VITE_CLAW_API_TOKEN ?? '',
      setBaseUrl: (baseUrl) => set({ baseUrl: normalizeBaseUrl(baseUrl) }),
      setApiToken: (apiToken) => set({ apiToken }),
      setConnection: ({ baseUrl, apiToken }) =>
        set({ baseUrl: normalizeBaseUrl(baseUrl), apiToken }),
      logout: () => set({ baseUrl: getDefaultBaseUrl(), apiToken: '' }),
    }),
    {
      name: 'ya-claw-connection',
    },
  ),
)
