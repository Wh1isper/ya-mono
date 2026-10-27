import { fetchEventSource } from '@microsoft/fetch-event-source'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { queryKeys } from '../../api/queryKeys'
import { useConnectionStore } from '../../stores/connectionStore'
import type { AguiEvent, RunSummary } from '../../types'
import type { StreamStatus } from '../../lib/status'
import { isTerminalAguiEvent } from './eventUtils'
import { LiveReplay } from './liveReplay'

const eventBatchIntervalMs = 32
class FatalRunStreamError extends Error {}

type StreamView = {
  connectionScope: string
  runId: string | null
  status: StreamStatus
  events: AguiEvent[]
  ready: boolean
}

type ReplayOwner = {
  connectionScope: string
  runId: string | null
  replay: LiveReplay
  cursor: number | null
  ready: boolean
  closed: boolean
}

export function useRunEventStream(
  runId: string | null,
  status: RunSummary['status'] | null,
  sessionId: string | null,
): { status: StreamStatus; events: AguiEvent[]; ready: boolean } {
  const baseUrl = useConnectionStore((state) => state.baseUrl)
  const apiToken = useConnectionStore((state) => state.apiToken)
  const connectionScope = useConnectionStore((state) => state.connectionScope)
  const invalidateConnection = useConnectionStore(
    (state) => state.invalidateConnection,
  )
  const queryClient = useQueryClient()
  const ownerRef = useRef<ReplayOwner | null>(null)
  const [streamState, setStreamState] = useState<StreamView>({
    connectionScope,
    runId,
    status: 'idle',
    events: [],
    ready: false,
  })

  useEffect(() => {
    if (
      ownerRef.current?.connectionScope !== connectionScope ||
      ownerRef.current?.runId !== runId
    ) {
      ownerRef.current = {
        connectionScope,
        runId,
        replay: new LiveReplay(),
        cursor: null,
        ready: false,
        closed: false,
      }
    }
    const owner = ownerRef.current
    const controller = new AbortController()
    const isCurrent = () =>
      !controller.signal.aborted && ownerRef.current === owner
    let flushTimer: ReturnType<typeof setTimeout> | null = null
    const publish = (nextStatus?: StreamStatus) => {
      if (flushTimer) clearTimeout(flushTimer)
      flushTimer = null
      if (!isCurrent()) return
      const events = owner.replay.snapshot()
      const ready = owner.ready
      setStreamState((previous) => ({
        connectionScope,
        runId,
        events,
        ready,
        status: nextStatus ?? previous.status,
      }))
    }
    const refresh = () => {
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.sessions }),
        sessionId
          ? queryClient.invalidateQueries({
              queryKey: queryKeys.session(sessionId),
            })
          : Promise.resolve(),
        sessionId
          ? queryClient.invalidateQueries({
              queryKey: queryKeys.sessionHistoryBase(sessionId),
            })
          : Promise.resolve(),
        queryClient.invalidateQueries({ queryKey: queryKeys.run(runId!) }),
      ])
    }
    const finish = () => {
      owner.closed = true
      publish('closed')
      refresh()
      controller.abort()
    }
    if (
      !runId ||
      (status !== 'running' && status !== 'queued') ||
      owner.closed
    ) {
      if (
        status !== null &&
        status !== 'running' &&
        status !== 'queued' &&
        !owner.closed
      ) {
        // A durable terminal status can arrive before the SSE terminal frame.
        // In that case the last live prefix is not authoritative anymore.
        owner.ready = false
        owner.closed = true
        refresh()
      }
      publish(runId ? 'closed' : 'idle')
      return () => controller.abort()
    }
    if (!apiToken.trim()) {
      publish('idle')
      return () => controller.abort()
    }
    publish('connecting')

    const streamPromise = fetchEventSource(
      `${baseUrl.replace(/\/$/, '')}/api/v1/runs/${encodeURIComponent(runId)}/events`,
      {
        signal: controller.signal,
        headers: {
          Authorization: `Bearer ${apiToken.trim()}`,
          ...(owner.cursor !== null
            ? { 'last-event-id': String(owner.cursor) }
            : {}),
        },
        openWhenHidden: true,
        async onopen(response) {
          if (!isCurrent()) return
          if (response.status === 404) {
            // The coordinator may already have released the terminal live handle.
            owner.ready = false
            finish()
            return
          }
          if (!response.ok) {
            if (response.status === 401) {
              invalidateConnection(
                'Your API token is invalid or expired.',
                connectionScope,
              )
            }
            const message = `run event stream failed with ${response.status}`
            if (response.status >= 400 && response.status < 500) {
              throw new FatalRunStreamError(message)
            }
            throw new Error(message)
          }
          publish('streaming')
        },
        onmessage(message) {
          if (!isCurrent() || !message.data) return
          let event: AguiEvent
          try {
            event = JSON.parse(message.data) as AguiEvent
          } catch (error) {
            console.warn('Ignored malformed run event', error)
            return
          }
          const cursor = message.id ? Number(message.id) : null
          if (event.type === 'claw.replay_snapshot') {
            if (
              event.runId !== runId ||
              !Array.isArray(event.events) ||
              cursor === null ||
              !Number.isSafeInteger(cursor)
            )
              return
            // Discard any unrendered prefix. The snapshot and its cursor form
            // one baseline; transport frames never enter the AGUI reducer.
            owner.replay.replace(event.events as AguiEvent[])
            owner.cursor = cursor
            owner.ready = true
            if (event.closed === true) finish()
            else publish('streaming')
            return
          }
          if (cursor !== null && Number.isSafeInteger(cursor)) {
            if (owner.cursor !== null && cursor <= owner.cursor) return
            owner.cursor = cursor
          }
          owner.replay.append(event)
          if (isTerminalAguiEvent(event)) finish()
          else if (!flushTimer)
            flushTimer = setTimeout(() => publish(), eventBatchIntervalMs)
        },
        onclose() {
          if (!isCurrent()) return
          publish('connecting')
          refresh()
          throw new Error('run event stream closed before terminal event')
        },
        onerror(error) {
          if (!isCurrent()) return
          if (error instanceof FatalRunStreamError) throw error
          publish('connecting')
          return 2_000
        },
      },
    )
    void streamPromise.catch((error: unknown) => {
      if (
        !isCurrent() ||
        (error instanceof Error && error.name === 'AbortError')
      )
        return
      publish('error')
    })

    return () => {
      // The owner holds accepted events and cursor together across effect
      // restarts (including queued -> running), even before the UI batch fires.
      controller.abort()
      if (flushTimer) clearTimeout(flushTimer)
    }
  }, [
    apiToken,
    baseUrl,
    connectionScope,
    invalidateConnection,
    queryClient,
    runId,
    sessionId,
    status,
  ])

  const ownsCurrentStream =
    streamState.connectionScope === connectionScope &&
    streamState.runId === runId
  return {
    status: ownsCurrentStream ? streamState.status : 'idle',
    events: ownsCurrentStream ? streamState.events : [],
    ready: ownsCurrentStream && streamState.ready,
  }
}
