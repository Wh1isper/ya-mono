import { LogOut, Save } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { useConnectionStore } from '../../stores/connectionStore'

export function SettingsPage() {
  const baseUrl = useConnectionStore((state) => state.baseUrl)
  const apiToken = useConnectionStore((state) => state.apiToken)
  const setConnection = useConnectionStore((state) => state.setConnection)
  const logout = useConnectionStore((state) => state.logout)
  const [draftBaseUrl, setDraftBaseUrl] = useState(baseUrl)
  const [draftToken, setDraftToken] = useState(apiToken)

  function saveConnection() {
    const normalizedBaseUrl = draftBaseUrl.trim().replace(/\/$/, '')
    const normalizedToken = draftToken.trim()
    if (!normalizedBaseUrl) {
      toast.error('Backend URL is required')
      return
    }
    if (!normalizedToken) {
      toast.error('API token is required')
      return
    }
    setConnection({ baseUrl: normalizedBaseUrl, apiToken: normalizedToken })
    toast.success('Connection saved')
  }

  return (
    <div className="p-6">
      <div className="max-w-3xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-sm font-medium text-blue-600">Connection</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">
          Settings
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          Configure the backend URL and bearer token used by the console.
        </p>

        <div className="mt-6 space-y-5">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">
              Backend URL
            </span>
            <input
              className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none ring-blue-600 transition focus:ring-2"
              value={draftBaseUrl}
              onChange={(event) => setDraftBaseUrl(event.target.value)}
              placeholder={
                typeof window !== 'undefined'
                  ? window.location.origin
                  : 'http://127.0.0.1:9042'
              }
              autoComplete="url"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-slate-700">
              API Token
            </span>
            <input
              className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none ring-blue-600 transition focus:ring-2"
              value={draftToken}
              onChange={(event) => setDraftToken(event.target.value)}
              type="password"
              placeholder="YA_CLAW_API_TOKEN"
              autoComplete="current-password"
            />
          </label>

          <div className="flex items-center gap-3">
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700"
              onClick={saveConnection}
            >
              <Save className="h-4 w-4" />
              Save connection
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50"
              onClick={logout}
            >
              <LogOut className="h-4 w-4" />
              Logout
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
