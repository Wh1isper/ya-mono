import { fetchEventSource } from '@microsoft/fetch-event-source'
import {
  Activity,
  Bot,
  CheckCircle2,
  Clock3,
  FilePenLine,
  Files,
  Hash,
  MessageSquare,
  PauseCircle,
  PlayCircle,
  Plus,
  RefreshCcw,
  Search,
  Send,
  Square,
  TerminalSquare,
  User,
  Wrench,
  XCircle,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Group, Panel, Separator } from 'react-resizable-panels'
import { toast } from 'sonner'

import {
  useCreateSessionMutation,
  useCreateSessionRunMutation,
  useProfilesQuery,
  useRunControlMutations,
  useRunQuery,
  useSessionQuery,
  useSessionsQuery,
} from '../../api/hooks'
import { queryKeys } from '../../api/queryKeys'
import { EmptyState } from '../../components/EmptyState'
import { JsonView } from '../../components/JsonView'
import { StatusBadge } from '../../components/StatusBadge'
import { cn, formatShortId } from '../../lib/utils'
import { useConnectionStore } from '../../stores/connectionStore'
import { useLayoutStore } from '../../stores/layoutStore'
import type {
  AguiEvent,
  InputPart,
  RunSummary,
  SessionSummary,
} from '../../types'
import { buildTimeline, reduceAguiEvent } from './agui/eventReducer'
import type { AguiTimelineState, TimelineBlock } from './agui/types'
import { useQueryClient } from '@tanstack/react-query'

type StreamStatus = 'idle' | 'connecting' | 'streaming' | 'closed' | 'error'

export function ChatPage() {
  const selectedSessionId = useLayoutStore((state) => state.selectedSessionId)
  const selectedRunId = useLayoutStore((state) => state.selectedRunId)
  const selectSession = useLayoutStore((state) => state.selectSession)
  const selectRun = useLayoutStore((state) => state.selectRun)
  const [sessionSearch, setSessionSearch] = useState('')
  const autoSelectedSessionRef = useRef(false)
  const sessions = useSessionsQuery()
  const selectedSession = useSessionQuery(selectedSessionId)
  const resolvedRunId =
    selectedRunId ??
    selectedSession.data?.session.active_run_id ??
    selectedSession.data?.session.head_run_id ??
    null
  const selectedRun = useRunQuery(resolvedRunId)
  const live = useRunEventStream(
    resolvedRunId,
    selectedRun.data?.run.status ?? null,
  )

  useEffect(() => {
    const firstSessionId = sessions.data?.[0]?.id
    if (
      !selectedSessionId &&
      firstSessionId &&
      !autoSelectedSessionRef.current
    ) {
      autoSelectedSessionRef.current = true
      selectSession(firstSessionId)
    }
  }, [selectSession, selectedSessionId, sessions.data])

  useEffect(() => {
    if (!selectedRunId) {
      const nextRunId =
        selectedSession.data?.session.active_run_id ??
        selectedSession.data?.session.head_run_id ??
        null
      if (nextRunId) selectRun(nextRunId)
    }
  }, [selectRun, selectedRunId, selectedSession.data])

  const filteredSessions = useMemo(() => {
    const needle = sessionSearch.trim().toLowerCase()
    const rows = sessions.data ?? []
    if (!needle) return rows
    return rows.filter((session) => {
      const haystack = [
        session.id,
        session.profile_name ?? '',
        session.project_id ?? '',
        session.latest_run?.input_preview ?? '',
        session.status,
      ]
        .join(' ')
        .toLowerCase()
      return haystack.includes(needle)
    })
  }, [sessionSearch, sessions.data])

  const timeline = useMemo(() => {
    const run =
      selectedRun.data?.run ??
      selectedSession.data?.session.runs.find(
        (item) => item.id === resolvedRunId,
      ) ??
      null
    const replay =
      selectedRun.data?.message ??
      run?.message ??
      selectedSession.data?.message ??
      []
    const inputParts = run?.input_parts ?? []
    const base = buildTimeline(
      replay,
      inputParts,
      run?.id ?? resolvedRunId ?? 'run',
    )
    if (!live.events.length) return base
    return live.events.reduce(
      (state, event) => reduceAguiEvent(state, event),
      base,
    )
  }, [live.events, resolvedRunId, selectedRun.data, selectedSession.data])

  const runs = selectedSession.data?.session.runs ?? []

  return (
    <div className="flex h-full min-h-0 flex-col bg-slate-100">
      <div className="border-b border-slate-200 bg-white px-5 py-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-blue-600">AGUI Console</p>
            <h1 className="mt-1 text-xl font-semibold tracking-tight text-slate-950">
              Chat Runtime
            </h1>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <LivePill status={live.status} eventCount={live.events.length} />
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 font-medium text-slate-700 shadow-sm transition hover:bg-slate-50"
              onClick={() => {
                selectSession(null)
                selectRun(null)
              }}
            >
              <Plus className="h-3.5 w-3.5" />
              New chat
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 font-medium text-slate-700 shadow-sm transition hover:bg-slate-50"
              onClick={() => sessions.refetch()}
            >
              <RefreshCcw className="h-3.5 w-3.5" />
              Refresh
            </button>
          </div>
        </div>
      </div>

      <Group orientation="horizontal" className="min-h-0 flex-1">
        <Panel defaultSize="42%" minSize="320px" maxSize="58%">
          <SessionList
            sessions={filteredSessions}
            selectedSessionId={selectedSessionId}
            search={sessionSearch}
            loading={sessions.isLoading}
            onSearchChange={setSessionSearch}
            onSelect={(session) => {
              selectSession(session.id)
              selectRun(
                session.active_run_id ??
                  session.head_run_id ??
                  session.latest_run?.id ??
                  null,
              )
            }}
          />
        </Panel>
        <ResizeHandle />
        <Panel defaultSize="58%" minSize="42%">
          <div className="flex h-full min-h-0 flex-col">
            <RunStrip
              runs={runs}
              selectedRunId={resolvedRunId}
              onSelectRun={selectRun}
            />
            <RunControlBar run={selectedRun.data?.run ?? null} />
            <TimelinePanel
              timeline={timeline}
              loading={selectedSession.isLoading || selectedRun.isLoading}
            />
            <Composer
              selectedSessionId={selectedSessionId}
              selectedProfile={
                selectedSession.data?.session.profile_name ?? null
              }
              sessionLocked={
                selectedSession.data?.session.status === 'queued' ||
                selectedSession.data?.session.status === 'running'
              }
            />
          </div>
        </Panel>
      </Group>
    </div>
  )
}

function SessionList({
  sessions,
  selectedSessionId,
  search,
  loading,
  onSearchChange,
  onSelect,
}: {
  sessions: SessionSummary[]
  selectedSessionId: string | null
  search: string
  loading: boolean
  onSearchChange: (value: string) => void
  onSelect: (session: SessionSummary) => void
}) {
  return (
    <aside className="flex h-full min-h-0 flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-200 p-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm outline-none ring-blue-600 transition focus:bg-white focus:ring-2"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search sessions"
          />
        </div>
      </div>
      <div className="scrollbar-thin min-h-0 flex-1 overflow-auto p-3">
        {loading ? <SessionSkeleton /> : null}
        {!loading && sessions.length === 0 ? (
          <EmptyState
            title="No sessions"
            description="Create a run from the composer to start chatting."
          />
        ) : null}
        <div className="space-y-2">
          {sessions.map((session) => (
            <button
              type="button"
              key={session.id}
              className={cn(
                'w-full rounded-2xl border p-3 text-left transition',
                selectedSessionId === session.id
                  ? 'border-blue-200 bg-blue-50 shadow-sm'
                  : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50',
              )}
              onClick={() => onSelect(session)}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="mono text-xs text-slate-500">
                    {formatShortId(session.id, 12)}
                  </p>
                  <p className="mt-1 line-clamp-2 text-sm font-medium leading-5 text-slate-900">
                    {session.latest_run?.input_preview ?? 'Empty session'}
                  </p>
                </div>
                <StatusBadge status={session.status} />
              </div>
              <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                <span>{session.profile_name ?? 'default'}</span>
                <span>{session.run_count} runs</span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </aside>
  )
}

function SessionSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 5 }).map((_, index) => (
        <div
          key={index}
          className="rounded-2xl border border-slate-200 bg-white p-3"
        >
          <div className="h-3 w-24 animate-pulse rounded bg-slate-100" />
          <div className="mt-3 h-4 w-full animate-pulse rounded bg-slate-100" />
          <div className="mt-2 h-4 w-2/3 animate-pulse rounded bg-slate-100" />
        </div>
      ))}
    </div>
  )
}

function RunStrip({
  runs,
  selectedRunId,
  onSelectRun,
}: {
  runs: RunSummary[]
  selectedRunId: string | null
  onSelectRun: (runId: string | null) => void
}) {
  return (
    <div className="flex h-14 shrink-0 items-center gap-2 border-b border-slate-200 bg-white px-4">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
        Runs
      </span>
      <div className="scrollbar-thin flex min-w-0 flex-1 gap-2 overflow-x-auto py-2">
        {runs.map((run) => (
          <button
            type="button"
            key={run.id}
            className={cn(
              'inline-flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition',
              selectedRunId === run.id
                ? 'border-blue-200 bg-blue-50 text-blue-700'
                : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
            )}
            onClick={() => onSelectRun(run.id)}
          >
            <Hash className="h-3 w-3" />
            {run.sequence_no}
            <span className="capitalize">{run.status}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

function RunControlBar({ run }: { run: RunSummary | null }) {
  const runControls = useRunControlMutations(run?.id ?? null)
  if (!run || (run.status !== 'queued' && run.status !== 'running')) return null

  return (
    <div className="flex items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3">
      <div className="flex items-center gap-2 text-sm text-slate-600">
        <StatusBadge status={run.status} />
        <span className="mono text-xs">{formatShortId(run.id, 12)}</span>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-700 transition hover:bg-amber-100 disabled:opacity-60"
          onClick={() => runControls.interrupt.mutate()}
          disabled={runControls.interrupt.isPending}
        >
          <PauseCircle className="h-3.5 w-3.5" />
          Interrupt
        </button>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700 transition hover:bg-rose-100 disabled:opacity-60"
          onClick={() => runControls.cancel.mutate()}
          disabled={runControls.cancel.isPending}
        >
          <Square className="h-3.5 w-3.5" />
          Cancel
        </button>
      </div>
    </div>
  )
}

function TimelinePanel({
  timeline,
  loading,
}: {
  timeline: AguiTimelineState
  loading: boolean
}) {
  const bottomRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [timeline.blocks.length])

  return (
    <section className="scrollbar-thin min-h-0 flex-1 overflow-auto bg-slate-50 p-5">
      {loading ? <TimelineSkeleton /> : null}
      {!loading && timeline.blocks.length === 0 ? (
        <EmptyState
          title="No replay yet"
          description="Select a run with committed AGUI messages or start a new turn."
        />
      ) : null}
      <div className="mx-auto max-w-4xl space-y-4">
        {timeline.blocks.map((block) => (
          <TimelineCard key={block.id} block={block} />
        ))}
        <div ref={bottomRef} />
      </div>
    </section>
  )
}

function TimelineSkeleton() {
  return (
    <div className="mx-auto max-w-4xl space-y-4">
      {Array.from({ length: 3 }).map((_, index) => (
        <div
          key={index}
          className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
        >
          <div className="h-4 w-32 animate-pulse rounded bg-slate-100" />
          <div className="mt-4 h-16 animate-pulse rounded bg-slate-100" />
        </div>
      ))}
    </div>
  )
}

function TimelineCard({ block }: { block: TimelineBlock }) {
  if (block.kind === 'user_input') {
    return (
      <Card icon={User} title="User input" accent="blue">
        <div className="space-y-2">
          {block.parts.map((part, index) => (
            <InputPartView key={index} part={part} />
          ))}
        </div>
      </Card>
    )
  }
  if (block.kind === 'assistant_message') {
    return (
      <Card
        icon={Bot}
        title={block.name ? `Assistant · ${block.name}` : 'Assistant'}
        accent="emerald"
      >
        <div className="whitespace-pre-wrap text-sm leading-7 text-slate-800">
          {block.content}
        </div>
      </Card>
    )
  }
  if (block.kind === 'reasoning') {
    return (
      <Card icon={Activity} title="Reasoning" accent="violet" subtle>
        <div className="whitespace-pre-wrap text-sm leading-7 text-slate-700">
          {block.content}
        </div>
      </Card>
    )
  }
  if (block.kind === 'tool_call') {
    return (
      <Card
        icon={Wrench}
        title={block.name ?? 'Tool call'}
        accent={block.status === 'failed' ? 'rose' : 'amber'}
      >
        <div className="space-y-3">
          <StatusBadge status={block.status} />
          {block.args ? (
            <CodeBlock label="Arguments" value={block.args} />
          ) : null}
          {block.result ? (
            <CodeBlock label="Result" value={block.result} />
          ) : null}
        </div>
      </Card>
    )
  }
  if (block.kind === 'task_board') {
    return (
      <Card icon={CheckCircle2} title="Task board" accent="blue">
        <div className="grid gap-2">
          {block.tasks.map((task) => (
            <div
              key={task.id}
              className="rounded-xl border border-slate-200 bg-slate-50 p-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-slate-900">
                    {task.subject}
                  </p>
                  {task.active_form ? (
                    <p className="mt-1 text-xs text-slate-500">
                      {task.active_form}
                    </p>
                  ) : null}
                </div>
                <StatusBadge status={task.status} />
              </div>
            </div>
          ))}
          {block.tasks.length === 0 ? (
            <p className="text-sm text-slate-500">No tasks in snapshot.</p>
          ) : null}
        </div>
      </Card>
    )
  }
  if (block.kind === 'context_meter') {
    const percent =
      block.contextWindowSize > 0
        ? Math.min(
            100,
            Math.round((block.totalTokens / block.contextWindowSize) * 100),
          )
        : 0
    return (
      <Card icon={Clock3} title="Context" accent="amber" compact>
        <div className="flex items-center gap-3">
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-amber-500"
              style={{ width: `${percent}%` }}
            />
          </div>
          <span className="mono text-xs text-slate-600">
            {block.totalTokens} / {block.contextWindowSize}
          </span>
        </div>
      </Card>
    )
  }
  if (block.kind === 'subagent') {
    return (
      <Card
        icon={Bot}
        title={`Subagent · ${block.agentName}`}
        accent={block.status === 'failed' ? 'rose' : 'violet'}
      >
        <StatusBadge status={block.status} />
        {block.promptPreview ? (
          <p className="mt-3 text-sm text-slate-600">{block.promptPreview}</p>
        ) : null}
        {block.resultPreview ? (
          <p className="mt-3 text-sm text-slate-800">{block.resultPreview}</p>
        ) : null}
        {block.error ? (
          <p className="mt-3 text-sm text-rose-700">{block.error}</p>
        ) : null}
      </Card>
    )
  }
  if (block.kind === 'file_change') {
    return (
      <Card
        icon={Files}
        title={
          block.toolName ? `File changes · ${block.toolName}` : 'File changes'
        }
        accent="emerald"
      >
        <JsonView value={block.changes} height="260px" />
      </Card>
    )
  }
  if (block.kind === 'note_snapshot') {
    return (
      <Card icon={FilePenLine} title="Notes" accent="blue">
        <JsonView value={block.entries} height="220px" />
      </Card>
    )
  }
  if (block.kind === 'usage') {
    return (
      <Card icon={Activity} title="Usage" accent="violet" compact>
        <JsonView value={block.payload} height="180px" />
      </Card>
    )
  }
  if (block.kind === 'runtime_event') {
    return (
      <Card
        icon={TerminalSquare}
        title={block.title}
        accent={accentFromRuntimeStatus(block.status)}
        compact
      >
        <JsonView value={block.payload} height="180px" />
      </Card>
    )
  }
  return (
    <Card icon={MessageSquare} title={block.name} accent="slate" compact>
      <JsonView value={block.payload} height="180px" />
    </Card>
  )
}

function Card({
  icon: Icon,
  title,
  accent,
  subtle,
  compact,
  children,
}: {
  icon: typeof Bot
  title: string
  accent: 'blue' | 'emerald' | 'amber' | 'rose' | 'violet' | 'slate'
  subtle?: boolean
  compact?: boolean
  children: React.ReactNode
}) {
  const accentClass = {
    blue: 'bg-blue-50 text-blue-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    amber: 'bg-amber-50 text-amber-600',
    rose: 'bg-rose-50 text-rose-600',
    violet: 'bg-violet-50 text-violet-600',
    slate: 'bg-slate-100 text-slate-600',
  }[accent]

  return (
    <article
      className={cn(
        'rounded-2xl border border-slate-200 bg-white shadow-sm',
        subtle && 'bg-white/70',
        compact ? 'p-3' : 'p-4',
      )}
    >
      <div className="mb-3 flex items-center gap-2">
        <span
          className={cn(
            'inline-flex h-8 w-8 items-center justify-center rounded-xl',
            accentClass,
          )}
        >
          <Icon className="h-4 w-4" />
        </span>
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      </div>
      {children}
    </article>
  )
}

function InputPartView({ part }: { part: InputPart }) {
  if (part.type === 'text')
    return (
      <div className="whitespace-pre-wrap rounded-xl bg-blue-50 p-3 text-sm leading-7 text-slate-800">
        {part.text}
      </div>
    )
  return <JsonView value={part} height="160px" />
}

function CodeBlock({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <pre className="scrollbar-thin max-h-60 overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs leading-5 text-slate-700">
        {formatMaybeJson(value)}
      </pre>
    </div>
  )
}

function formatMaybeJson(value: string) {
  try {
    return JSON.stringify(JSON.parse(value), null, 2)
  } catch {
    return value
  }
}

function Composer({
  selectedSessionId,
  selectedProfile,
  sessionLocked,
}: {
  selectedSessionId: string | null
  selectedProfile: string | null
  sessionLocked: boolean
}) {
  const [text, setText] = useState('')
  const [profileName, setProfileName] = useState(selectedProfile ?? '')
  const [projectId, setProjectId] = useState('')
  const createSession = useCreateSessionMutation()
  const createRun = useCreateSessionRunMutation(selectedSessionId)
  const profiles = useProfilesQuery()
  const selectSession = useLayoutStore((store) => store.selectSession)
  const selectRun = useLayoutStore((store) => store.selectRun)

  useEffect(() => {
    setProfileName(selectedProfile ?? '')
  }, [selectedProfile])

  const isPending = createSession.isPending || createRun.isPending
  const canSend = text.trim().length > 0 && !isPending

  async function send() {
    const normalizedText = text.trim()
    if (!normalizedText) return
    const inputParts: InputPart[] = [{ type: 'text', text: normalizedText }]
    try {
      if (selectedSessionId) {
        const run = await createRun.mutateAsync({ input_parts: inputParts })
        selectRun(run.id)
      } else {
        const response = await createSession.mutateAsync({
          profile_name: profileName.trim() || null,
          project_id: projectId.trim() || null,
          input_parts: inputParts,
        })
        selectSession(response.session.id)
        selectRun(
          response.run?.id ??
            response.session.active_run_id ??
            response.session.head_run_id ??
            null,
        )
      }
      setText('')
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'Failed to send message',
      )
    }
  }

  return (
    <div className="border-t border-slate-200 bg-white p-4">
      <div className="mx-auto max-w-4xl">
        <div className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
          <textarea
            className="max-h-48 min-h-24 w-full resize-none rounded-xl border-0 p-2 text-sm leading-6 text-slate-900 outline-none placeholder:text-slate-400"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Send a message to YA Claw..."
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                void send()
              }
            }}
          />
          <div className="flex items-center justify-between gap-3 border-t border-slate-100 pt-3">
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <select
                className="max-w-52 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700 outline-none ring-blue-600 focus:ring-2"
                value={profileName}
                onChange={(event) => setProfileName(event.target.value)}
                disabled={Boolean(selectedSessionId) || sessionLocked}
              >
                <option value="">default profile</option>
                {(profiles.data ?? []).map((profile) => (
                  <option key={profile.name} value={profile.name}>
                    {profile.name}
                  </option>
                ))}
              </select>
              <input
                className="max-w-52 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700 outline-none ring-blue-600 focus:ring-2"
                value={projectId}
                onChange={(event) => setProjectId(event.target.value)}
                placeholder="project id"
                disabled={Boolean(selectedSessionId) || sessionLocked}
              />
            </div>
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:bg-slate-300"
              disabled={!canSend}
              onClick={() => void send()}
            >
              {selectedSessionId ? (
                <Send className="h-4 w-4" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              {selectedSessionId ? 'Send' : 'New session'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function LivePill({
  status,
  eventCount,
}: {
  status: StreamStatus
  eventCount: number
}) {
  const icon =
    status === 'streaming'
      ? PlayCircle
      : status === 'error'
        ? XCircle
        : status === 'closed'
          ? CheckCircle2
          : Clock3
  const Icon = icon
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full border px-3 py-1.5 font-medium capitalize',
        status === 'streaming' &&
          'border-emerald-200 bg-emerald-50 text-emerald-700',
        status === 'connecting' &&
          'border-amber-200 bg-amber-50 text-amber-700',
        status === 'error' && 'border-rose-200 bg-rose-50 text-rose-700',
        (status === 'idle' || status === 'closed') &&
          'border-slate-200 bg-white text-slate-600',
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {status} · {eventCount} live
    </span>
  )
}

function ResizeHandle() {
  return (
    <Separator className="group relative w-1 bg-slate-100 transition hover:bg-blue-100">
      <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-slate-200 group-hover:bg-blue-300" />
    </Separator>
  )
}

function accentFromRuntimeStatus(
  status: 'info' | 'running' | 'success' | 'warning' | 'error',
) {
  if (status === 'running') return 'amber'
  if (status === 'success') return 'emerald'
  if (status === 'warning') return 'amber'
  if (status === 'error') return 'rose'
  return 'slate'
}

function useRunEventStream(
  runId: string | null,
  status: RunSummary['status'] | null,
): { status: StreamStatus; events: AguiEvent[] } {
  const baseUrl = useConnectionStore((state) => state.baseUrl)
  const apiToken = useConnectionStore((state) => state.apiToken)
  const queryClient = useQueryClient()
  const [streamStatus, setStreamStatus] = useState<StreamStatus>('idle')
  const [events, setEvents] = useState<AguiEvent[]>([])

  useEffect(() => {
    setEvents([])
  }, [runId])

  useEffect(() => {
    if (!runId || (status !== 'running' && status !== 'queued')) {
      setStreamStatus(runId ? 'closed' : 'idle')
      return
    }
    if (!apiToken.trim()) {
      setStreamStatus('idle')
      return
    }

    const controller = new AbortController()
    setStreamStatus('connecting')

    void fetchEventSource(
      `${baseUrl.replace(/\/$/, '')}/api/v1/runs/${encodeURIComponent(runId)}/events`,
      {
        signal: controller.signal,
        headers: { Authorization: `Bearer ${apiToken.trim()}` },
        openWhenHidden: true,
        async onopen(response) {
          if (!response.ok) {
            setStreamStatus('error')
            throw new Error(`run event stream failed with ${response.status}`)
          }
          setStreamStatus('streaming')
        },
        onmessage(message) {
          if (!message.data) return
          const event = JSON.parse(message.data) as AguiEvent
          setEvents((previous) => [...previous, event])
          const eventType = typeof event.type === 'string' ? event.type : ''
          if (eventType === 'RUN_FINISHED' || eventType === 'RUN_ERROR') {
            void queryClient.invalidateQueries({
              queryKey: queryKeys.run(runId),
            })
            setStreamStatus('closed')
          }
        },
        onclose() {
          setStreamStatus('closed')
        },
        onerror(error) {
          if (!controller.signal.aborted) setStreamStatus('error')
          throw error
        },
      },
    )

    return () => {
      controller.abort()
    }
  }, [apiToken, baseUrl, queryClient, runId, status])

  return { status: streamStatus, events }
}
