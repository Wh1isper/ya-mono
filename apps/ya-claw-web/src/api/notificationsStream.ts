import { fetchEventSource } from '@microsoft/fetch-event-source'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { useConnectionStore } from '../stores/connectionStore'
import type { NotificationEvent } from '../types'
import { queryKeys } from './queryKeys'

export type NotificationStatus = 'idle' | 'connecting' | 'connected' | 'error'

export function useNotificationStream() {
  const baseUrl = useConnectionStore((state) => state.baseUrl)
  const apiToken = useConnectionStore((state) => state.apiToken)
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<NotificationStatus>('idle')
  const lastEventIdRef = useRef<string | null>(null)

  useEffect(() => {
    if (!apiToken.trim()) {
      setStatus('idle')
      return
    }

    const controller = new AbortController()
    setStatus('connecting')

    void fetchEventSource(
      `${baseUrl.replace(/\/$/, '')}/api/v1/claw/notifications`,
      {
        signal: controller.signal,
        headers: {
          Authorization: `Bearer ${apiToken.trim()}`,
          ...(lastEventIdRef.current
            ? { 'Last-Event-ID': lastEventIdRef.current }
            : {}),
        },
        openWhenHidden: true,
        async onopen(response) {
          if (!response.ok) {
            setStatus('error')
            throw new Error(
              `notification stream failed with ${response.status}`,
            )
          }
          setStatus('connected')
        },
        onmessage(message) {
          if (message.id) {
            lastEventIdRef.current = message.id
          }
          if (!message.data) return
          const event = JSON.parse(message.data) as NotificationEvent
          invalidateForNotification(queryClient, event)
        },
        onerror(error) {
          setStatus('error')
          throw error
        },
      },
    )

    return () => {
      controller.abort()
    }
  }, [apiToken, baseUrl, queryClient])

  return status
}

function invalidateForNotification(
  queryClient: ReturnType<typeof useQueryClient>,
  event: NotificationEvent,
) {
  const sessionId =
    typeof event.payload.session_id === 'string'
      ? event.payload.session_id
      : null
  const runId =
    typeof event.payload.run_id === 'string' ? event.payload.run_id : null
  const profileName =
    typeof event.payload.profile_name === 'string'
      ? event.payload.profile_name
      : null

  if (event.type.startsWith('session.') || event.type.startsWith('run.')) {
    void queryClient.invalidateQueries({ queryKey: queryKeys.sessions })
    if (sessionId)
      void queryClient.invalidateQueries({
        queryKey: queryKeys.session(sessionId),
      })
    if (runId) {
      void queryClient.invalidateQueries({ queryKey: queryKeys.run(runId) })
      void queryClient.invalidateQueries({
        queryKey: queryKeys.runTrace(runId),
      })
    }
  }

  if (event.type.startsWith('profile.') || event.type === 'profiles.seeded') {
    void queryClient.invalidateQueries({ queryKey: queryKeys.profiles })
    if (profileName)
      void queryClient.invalidateQueries({
        queryKey: queryKeys.profile(profileName),
      })
  }
}
