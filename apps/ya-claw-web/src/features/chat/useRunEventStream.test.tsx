import { fetchEventSource } from '@microsoft/fetch-event-source'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useConnectionStore } from '../../stores/connectionStore'
import type { AguiEvent, RunSummary } from '../../types'
import type { StreamStatus } from '../../lib/status'
import { useRunEventStream } from './useRunEventStream'

vi.mock('@microsoft/fetch-event-source', () => ({
  fetchEventSource: vi.fn(() => new Promise<void>(() => undefined)),
}))

type StreamObservation = {
  runId: string | null
  status: StreamStatus
  events: AguiEvent[]
  ready: boolean
}

const observations: StreamObservation[] = []

function Probe({
  runId,
  status,
}: {
  runId: string | null
  status: RunSummary['status'] | null
}) {
  const stream = useRunEventStream(runId, status, 'session-1')
  observations.push({ runId, ...stream })
  return null
}

function streamMessage(messageId: string, delta: string, id = '') {
  return {
    data: JSON.stringify({
      type: 'TEXT_MESSAGE_CHUNK',
      message_id: messageId,
      delta,
    }),
    event: '',
    id,
    retry: undefined,
  }
}

function Wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      {children}
    </QueryClientProvider>
  )
}

describe('useRunEventStream ownership', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    observations.length = 0
    useConnectionStore.setState({
      baseUrl: 'https://claw.example',
      apiToken: 'test-token',
      connectionScope: 'stream-owner-test',
      connectionIssue: null,
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('replaces pending deltas atomically and preserves more than 1000 chunks', async () => {
    render(<Probe runId="run-a" status="running" />, { wrapper: Wrapper })
    const options = vi.mocked(fetchEventSource).mock.calls[0]![1]!
    await act(async () => {
      options.onmessage?.(streamMessage('text', 'stale pending', '1'))
      options.onmessage?.({
        data: JSON.stringify({
          type: 'claw.replay_snapshot',
          runId: 'run-a',
          events: [
            {
              type: 'TEXT_MESSAGE_CHUNK',
              message_id: 'text',
              delta: 'prefix:',
            },
          ],
          closed: false,
        }),
        event: 'claw.replay_snapshot',
        id: '100',
        retry: undefined,
      })
      options.onmessage?.(streamMessage('text', 'duplicate', '100'))
      for (let index = 101; index <= 2100; index++) {
        options.onmessage?.(streamMessage('text', 'x', String(index)))
      }
      vi.advanceTimersByTime(32)
    })
    expect(observations[observations.length - 1]?.events).toEqual([
      {
        type: 'TEXT_MESSAGE_CHUNK',
        message_id: 'text',
        delta: `prefix:${'x'.repeat(2000)}`,
      },
    ])
  })

  it('keeps accepted but unrendered chunks and the cursor across queued to running', async () => {
    const view = render(<Probe runId="run-a" status="queued" />, {
      wrapper: Wrapper,
    })
    const first = vi.mocked(fetchEventSource).mock.calls[0]![1]!
    await act(async () => {
      first.onmessage?.({
        data: JSON.stringify({
          type: 'claw.replay_snapshot',
          runId: 'run-a',
          events: [],
          closed: false,
        }),
        event: 'claw.replay_snapshot',
        id: '0',
        retry: undefined,
      })
      first.onmessage?.(streamMessage('text', 'accepted', '1'))
    })
    view.rerender(<Probe runId="run-a" status="running" />)
    const second = vi.mocked(fetchEventSource).mock.calls[1]![1]!
    expect(second.headers).toMatchObject({ 'last-event-id': '1' })
    await act(async () => {
      second.onmessage?.(streamMessage('text', 'duplicate', '1'))
      second.onmessage?.(streamMessage('text', ' next', '2'))
      expect(second.onerror?.(new Error('network'))).toBe(2000)
      vi.advanceTimersByTime(32)
    })
    expect(observations[observations.length - 1]?.events[0]?.delta).toBe(
      'accepted next',
    )
    expect(first.signal?.aborted).toBe(true)
  })

  it('closes and refreshes durable queries on a terminal snapshot', async () => {
    const invalidate = vi.spyOn(QueryClient.prototype, 'invalidateQueries')
    render(<Probe runId="run-a" status="running" />, { wrapper: Wrapper })
    const options = vi.mocked(fetchEventSource).mock.calls[0]![1]!
    await act(async () => {
      options.onmessage?.({
        data: JSON.stringify({
          type: 'claw.replay_snapshot',
          runId: 'run-a',
          events: [
            {
              type: 'TEXT_MESSAGE_CHUNK',
              messageId: 'text',
              delta: 'complete',
            },
          ],
          closed: true,
        }),
        event: 'claw.replay_snapshot',
        id: '99',
        retry: undefined,
      })
      options.onclose?.()
    })
    expect(observations[observations.length - 1]).toMatchObject({
      status: 'closed',
      events: [{ delta: 'complete' }],
    })
    expect(options.signal?.aborted).toBe(true)
    expect(invalidate).toHaveBeenCalledTimes(4)
    invalidate.mockRestore()
  })

  it.each(['failed', 'cancelled', 'completed'] as const)(
    'releases an incomplete live prefix when durable status becomes %s',
    async (status) => {
      const invalidate = vi.spyOn(QueryClient.prototype, 'invalidateQueries')
      const view = render(<Probe runId="run-a" status="running" />, {
        wrapper: Wrapper,
      })
      const options = vi.mocked(fetchEventSource).mock.calls[0]![1]!
      await act(async () => {
        options.onmessage?.({
          data: JSON.stringify({
            type: 'claw.replay_snapshot',
            runId: 'run-a',
            events: [],
            closed: false,
          }),
          event: 'claw.replay_snapshot',
          id: '0',
          retry: undefined,
        })
        options.onmessage?.(streamMessage('text', 'incomplete', '1'))
        vi.advanceTimersByTime(32)
      })
      expect(observations[observations.length - 1]?.ready).toBe(true)
      view.rerender(<Probe runId="run-a" status={status} />)
      expect(observations[observations.length - 1]).toMatchObject({
        ready: false,
        status: 'closed',
      })
      expect(options.signal?.aborted).toBe(true)
      expect(invalidate).toHaveBeenCalledWith({
        queryKey: ['session-history', 'session-1'],
      })
      invalidate.mockRestore()
    },
  )

  it('releases the live prefix when the server has already removed the handle', async () => {
    render(<Probe runId="run-a" status="running" />, { wrapper: Wrapper })
    const options = vi.mocked(fetchEventSource).mock.calls[0]![1]!
    await act(async () => {
      options.onmessage?.({
        data: JSON.stringify({
          type: 'claw.replay_snapshot',
          runId: 'run-a',
          events: [],
          closed: false,
        }),
        event: 'claw.replay_snapshot',
        id: '0',
        retry: undefined,
      })
    })
    expect(observations[observations.length - 1]?.ready).toBe(true)
    await act(async () => {
      await options.onopen?.(new Response(null, { status: 404 }))
    })
    expect(observations[observations.length - 1]).toMatchObject({
      ready: false,
      status: 'closed',
    })
  })

  it('sends only the latest cursor on a real transport retry after an effect restart', async () => {
    const real = await vi.importActual<
      typeof import('@microsoft/fetch-event-source')
    >('@microsoft/fetch-event-source')
    const view = render(<Probe runId="run-a" status="queued" />, {
      wrapper: Wrapper,
    })
    const first = vi.mocked(fetchEventSource).mock.calls[0]![1]!
    await act(async () => {
      first.onmessage?.({
        data: JSON.stringify({
          type: 'claw.replay_snapshot',
          runId: 'run-a',
          events: [],
          closed: false,
        }),
        event: 'claw.replay_snapshot',
        id: '1',
        retry: undefined,
      })
    })
    const headers: Headers[] = []
    const transport = vi
      .fn<typeof fetch>()
      .mockImplementation(async (_input, init) => {
        headers.push(new Headers(init?.headers))
        if (headers.length > 1) return new Promise<Response>(() => undefined)
        return new Response(
          `id: 2\ndata: ${streamMessage('text', 'next').data}\n\n`,
          {
            headers: { 'content-type': 'text/event-stream' },
          },
        )
      })
    vi.mocked(fetchEventSource).mockImplementationOnce((input, options) =>
      real.fetchEventSource(input, { ...options, fetch: transport }),
    )
    await act(async () => {
      view.rerender(<Probe runId="run-a" status="running" />)
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000)
    })
    expect(headers.map((value) => value.get('last-event-id'))).toEqual([
      '1',
      '2',
    ])
    view.unmount()
  })

  it('retries unexpected closes but treats authentication failure as fatal', async () => {
    render(<Probe runId="run-a" status="running" />, { wrapper: Wrapper })
    const options = vi.mocked(fetchEventSource).mock.calls[0]![1]!
    await act(async () => {
      expect(() => options.onclose?.()).toThrow('closed before terminal')
      expect(options.onerror?.(new Error('network'))).toBe(2000)
      let failure: unknown
      try {
        await options.onopen?.(new Response(null, { status: 401 }))
      } catch (error) {
        failure = error
      }
      expect(failure).toBeInstanceOf(Error)
      expect(options.signal?.aborted).toBe(true)
      expect(useConnectionStore.getState().connectionIssue).not.toBeNull()
    })
  })

  it('isolates events, callbacks, timers, and status by run and connection scope', async () => {
    const view = render(<Probe runId="run-a" status="running" />, {
      wrapper: Wrapper,
    })
    expect(fetchEventSource).toHaveBeenCalledOnce()

    const runAOptions = vi.mocked(fetchEventSource).mock.calls[0]?.[1]
    await act(async () => {
      await runAOptions?.onopen?.(new Response(null, { status: 200 }))
      runAOptions?.onmessage?.(streamMessage('message-a', 'event from run A'))
      vi.advanceTimersByTime(32)
    })

    const latestRunA = observations[observations.length - 1]
    expect(latestRunA).toMatchObject({
      runId: 'run-a',
      status: 'streaming',
    })
    expect(latestRunA?.events).toHaveLength(1)

    runAOptions?.onmessage?.(
      streamMessage('pending-message-a', 'pending event from run A'),
    )
    observations.length = 0
    view.rerender(<Probe runId="run-b" status="running" />)

    expect(observations[0]).toEqual({
      runId: 'run-b',
      status: 'idle',
      events: [],
      ready: false,
    })
    expect(fetchEventSource).toHaveBeenCalledTimes(2)
    const runBOptions = vi.mocked(fetchEventSource).mock.calls[1]?.[1]
    await act(async () => {
      await runBOptions?.onopen?.(new Response(null, { status: 200 }))
      runBOptions?.onmessage?.(streamMessage('message-b', 'event from run B'))
      vi.advanceTimersByTime(32)
    })
    expect(observations[observations.length - 1]).toMatchObject({
      runId: 'run-b',
      status: 'streaming',
      events: [{ message_id: 'message-b' }],
    })

    await act(async () => {
      await runAOptions?.onopen?.(new Response(null, { status: 200 }))
      runAOptions?.onmessage?.(
        streamMessage('stale-message-a', 'late event from run A'),
      )
      runAOptions?.onclose?.()
      runAOptions?.onerror?.(new Error('late run A stream error'))
      vi.advanceTimersByTime(64)
    })
    expect(observations[observations.length - 1]).toMatchObject({
      runId: 'run-b',
      status: 'streaming',
      events: [{ message_id: 'message-b' }],
    })

    runBOptions?.onmessage?.(
      streamMessage('pending-message-b', 'pending old-scope event'),
    )
    observations.length = 0
    act(() => {
      useConnectionStore.setState({ connectionScope: 'stream-owner-test-2' })
    })

    expect(observations[0]).toEqual({
      runId: 'run-b',
      status: 'idle',
      events: [],
      ready: false,
    })
    expect(fetchEventSource).toHaveBeenCalledTimes(3)
    const newScopeOptions = vi.mocked(fetchEventSource).mock.calls[2]?.[1]
    await act(async () => {
      await newScopeOptions?.onopen?.(new Response(null, { status: 200 }))
      newScopeOptions?.onmessage?.(
        streamMessage('message-new-scope', 'event from new scope'),
      )
      vi.advanceTimersByTime(32)
    })

    await act(async () => {
      await runBOptions?.onopen?.(new Response(null, { status: 200 }))
      runBOptions?.onmessage?.(
        streamMessage('stale-message-b', 'late old-scope event'),
      )
      runBOptions?.onclose?.()
      runBOptions?.onerror?.(new Error('late old-scope stream error'))
      vi.advanceTimersByTime(64)
    })
    expect(observations[observations.length - 1]).toMatchObject({
      runId: 'run-b',
      status: 'streaming',
      events: [{ message_id: 'message-new-scope' }],
    })
  })
})
