import type { AguiEvent, RunSummary, SessionGetResponse } from '../../types'
import { buildTimelineFromRuns, reduceAguiEvent } from './agui/eventReducer'
import type { AguiTimelineState } from './agui/types'

export type SessionHistoryState = {
  runs: RunSummary[]
  timeline: AguiTimelineState
  events: AguiEvent[]
  hasMore: boolean
  loadedRunCount: number
  totalRunCount: number
  oldestSequenceNo: number | null
}

export type LiveRunReplay = {
  runId: string | null
  ready: boolean
  events: AguiEvent[]
}

export function mergeSessionHistoryPages(
  pages: SessionGetResponse[] | undefined,
  live?: LiveRunReplay,
): SessionHistoryState {
  const latestPage = pages?.[0]
  const orderedRuns = orderRunsForTimeline(dedupeRuns(pages))
  const replayRuns = orderedRuns.map((run) =>
    live?.ready && run.id === live.runId
      ? { ...run, message: live.events }
      : run,
  )
  // A newly admitted run may not have reached the session query yet.
  const trailingEvents =
    live?.ready && !orderedRuns.some((run) => run.id === live.runId)
      ? live.events
      : []
  const baseTimeline = buildTimelineFromRuns(replayRuns, {
    includeRuntimeEvents: false,
  })
  const timeline = trailingEvents.reduce(
    (state, event) =>
      reduceAguiEvent(state, event, { includeRuntimeEvents: false }),
    baseTimeline,
  )
  return {
    runs: orderedRuns,
    timeline,
    events: [
      ...replayRuns.flatMap((run) => run.message ?? []),
      ...trailingEvents,
    ],
    hasMore: Boolean(pages?.[pages.length - 1]?.session.runs_has_more),
    loadedRunCount: orderedRuns.length,
    totalRunCount: latestPage?.session.run_count ?? orderedRuns.length,
    oldestSequenceNo: orderedRuns[0]?.sequence_no ?? null,
  }
}

export function latestRunFromHistory(
  runs: RunSummary[],
  fallbackRunId: string | null,
) {
  return (
    runs.find((run) => run.id === fallbackRunId) ??
    [...runs].sort((left, right) => right.sequence_no - left.sequence_no)[0] ??
    null
  )
}

function dedupeRuns(pages: SessionGetResponse[] | undefined) {
  const byId = new Map<string, RunSummary>()
  for (const page of pages ?? []) {
    for (const run of page.session.runs) {
      byId.set(run.id, { ...byId.get(run.id), ...run })
    }
  }
  return [...byId.values()]
}

function orderRunsForTimeline(runs: RunSummary[]) {
  return [...runs].sort((left, right) => {
    if (left.sequence_no !== right.sequence_no) {
      return left.sequence_no - right.sequence_no
    }
    return left.id.localeCompare(right.id)
  })
}
