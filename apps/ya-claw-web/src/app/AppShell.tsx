import {
  Bot,
  CalendarClock,
  HeartPulse,
  Home,
  LogOut,
  Settings,
  SlidersHorizontal,
} from 'lucide-react'

import { useHealthQuery } from '../api/hooks'
import { useNotificationStream } from '../api/notificationsStream'
import { cn } from '../lib/utils'
import { useConnectionStore } from '../stores/connectionStore'
import { type AppRoute, useLayoutStore } from '../stores/layoutStore'
import { ChatPage } from '../features/chat/ChatPage'
import { HeartbeatPage } from '../features/heartbeat/HeartbeatPage'
import { OverviewPage } from '../features/overview/OverviewPage'
import { ProfilesPage } from '../features/profiles/ProfilesPage'
import { SchedulesPage } from '../features/schedules/SchedulesPage'
import { SettingsPage } from '../features/settings/SettingsPage'

const navItems: Array<{ route: AppRoute; label: string; icon: typeof Home }> = [
  { route: 'overview', label: 'Overview', icon: Home },
  { route: 'chat', label: 'Chat', icon: Bot },
  { route: 'schedules', label: 'Schedules', icon: CalendarClock },
  { route: 'heartbeat', label: 'Heartbeat', icon: HeartPulse },
  { route: 'profiles', label: 'Profiles', icon: SlidersHorizontal },
  { route: 'settings', label: 'Settings', icon: Settings },
]

export function AppShell() {
  const route = useLayoutStore((state) => state.route)
  const setRoute = useLayoutStore((state) => state.setRoute)
  const baseUrl = useConnectionStore((state) => state.baseUrl)
  const apiToken = useConnectionStore((state) => state.apiToken)
  const logout = useConnectionStore((state) => state.logout)
  const health = useHealthQuery()
  const notificationStatus = useNotificationStream()

  return (
    <div className="flex min-h-screen bg-slate-100 text-slate-950">
      <aside className="flex w-64 shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="border-b border-slate-200 p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-blue-600 text-sm font-semibold text-white">
              YA
            </div>
            <div>
              <p className="font-semibold tracking-tight">YA Claw</p>
              <p className="text-xs text-slate-500">Runtime Console</p>
            </div>
          </div>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {navItems.map((item) => {
            const Icon = item.icon
            const active = route === item.route
            return (
              <button
                key={item.route}
                type="button"
                className={cn(
                  'flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition',
                  active
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-950',
                )}
                onClick={() => setRoute(item.route)}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </button>
            )
          })}
        </nav>
        <div className="border-t border-slate-200 p-4 text-xs text-slate-500">
          <p className="truncate mono">{baseUrl}</p>
          <p className="mt-1">
            Token {apiToken.trim() ? 'configured' : 'missing'}
          </p>
          <button
            type="button"
            className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50"
            onClick={logout}
          >
            <LogOut className="h-4 w-4" />
            Logout
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white/90 px-5 backdrop-blur">
          <div className="flex items-center gap-3 text-sm">
            <StatusDot
              status={
                health.data?.status === 'ok'
                  ? 'ok'
                  : health.isError
                    ? 'error'
                    : 'pending'
              }
            />
            <span className="font-medium">
              Backend{' '}
              {health.data?.status ??
                (health.isError ? 'unavailable' : 'checking')}
            </span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-500">
              Notifications {notificationStatus}
            </span>
          </div>
          <div className="text-xs text-slate-500">Light Workbench</div>
        </header>

        <main className="min-h-0 flex-1 overflow-hidden">
          {route === 'overview' ? <OverviewPage /> : null}
          {route === 'chat' ? <ChatPage /> : null}
          {route === 'schedules' ? <SchedulesPage /> : null}
          {route === 'heartbeat' ? <HeartbeatPage /> : null}
          {route === 'profiles' ? <ProfilesPage /> : null}
          {route === 'settings' ? <SettingsPage /> : null}
        </main>
      </div>
    </div>
  )
}

function StatusDot({ status }: { status: 'ok' | 'pending' | 'error' }) {
  return (
    <span
      className={cn(
        'h-2.5 w-2.5 rounded-full',
        status === 'ok' && 'bg-emerald-500',
        status === 'pending' && 'bg-amber-500',
        status === 'error' && 'bg-rose-500',
      )}
    />
  )
}
