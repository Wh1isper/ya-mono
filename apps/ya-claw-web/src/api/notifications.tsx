import type { ReactNode } from 'react'

import { useNotificationStream } from './notificationsStream'

export function NotificationProvider({ children }: { children: ReactNode }) {
  useNotificationStream()
  return children
}
