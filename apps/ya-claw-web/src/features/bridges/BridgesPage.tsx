import { Bot, MessageSquare, RefreshCcw, Route, Send } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import {
  useBridgeConversationsQuery,
  useBridgeEventsQuery,
} from '../../api/hooks'
import { EmptyState } from '../../components/EmptyState'
import { JsonView } from '../../components/JsonView'
import { StatusBadge } from '../../components/StatusBadge'
import { cn, formatShortId } from '../../lib/utils'
import { useLayoutStore } from '../../stores/layoutStore'
import type {
  BridgeConversationSummary,
  BridgeEventStatus,
  BridgeEventSummary,
} from '../../types'

const statusOptions: Array<BridgeEventStatus | 'all'> = [
  'all',
  'received',
  'queued',
  'submitted',
  'steered',
  'duplicate',
  'failed',
]

export function BridgesPage() {
  const conversations = useBridgeConversationsQuery()
  const [selectedConversationId, setSelectedConversationId] = useState<
    string | null
  >(null)
  const [statusFilter, setStatusFilter] = useState<BridgeEventStatus | 'all'>(
    'all',
  )
  const events = useBridgeEventsQuery({
    conversationId: selectedConversationId,
    status: statusFilter,
  })
  const conversationRows = useMemo(
    () => conversations.data?.conversations ?? [],
    [conversations.data?.conversations],
  )
  const selectedConversation = useMemo(
    () =>
      conversationRows.find((item) => item.id === selectedConversationId) ??
      null,
    [conversationRows, selectedConversationId],
  )

  useEffect(() => {
    if (!selectedConversationId && conversationRows[0]) {
      setSelectedConversationId(conversationRows[0].id)
    }
  }, [conversationRows, selectedConversationId])

  return (
    <div className="flex h-full min-h-0 bg-slate-100">
      <aside className="flex w-[28rem] shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="border-b border-slate-200 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-blue-600">
                Inbound delivery
              </p>
              <h1 className="mt-1 text-xl font-semibold tracking-tight text-slate-950">
                Bridge Conversations
              </h1>
            </div>
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition hover:bg-slate-50"
              onClick={() => void conversations.refetch()}
            >
              <RefreshCcw className="h-3.5 w-3.5" />
              Refresh
            </button>
          </div>
        </div>
        <div className="scrollbar-thin min-h-0 flex-1 overflow-auto p-3">
          {conversations.isLoading ? <ConversationSkeleton /> : null}
          {!conversations.isLoading && conversationRows.length === 0 ? (
            <EmptyState
              title="No bridge conversations"
              description="Accepted bridge messages create conversation records here."
            />
          ) : null}
          <div className="space-y-2">
            {conversationRows.map((conversation) => (
              <ConversationListItem
                key={conversation.id}
                conversation={conversation}
                active={selectedConversationId === conversation.id}
                onClick={() => setSelectedConversationId(conversation.id)}
              />
            ))}
          </div>
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-6xl space-y-6">
          <BridgeMetrics
            conversations={conversationRows}
            events={events.data?.events ?? []}
          />
          <ConversationDetail conversation={selectedConversation} />
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-slate-950">
                  Bridge event delivery
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  Status shows whether each inbound event created a run, queued
                  a run, steered an active run, duplicated, or failed.
                </p>
              </div>
              <select
                className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700 outline-none ring-blue-600 focus:ring-2"
                value={statusFilter}
                onChange={(event) =>
                  setStatusFilter(
                    event.target.value as BridgeEventStatus | 'all',
                  )
                }
              >
                {statusOptions.map((status) => (
                  <option key={status} value={status}>
                    {status.replace(/_/g, ' ')}
                  </option>
                ))}
              </select>
            </div>
            <div className="mt-4 space-y-2">
              {events.isLoading ? <EventSkeleton /> : null}
              {!events.isLoading && (events.data?.events ?? []).length === 0 ? (
                <EmptyState
                  title="No bridge events"
                  description="Select a conversation or adjust the status filter."
                />
              ) : null}
              {(events.data?.events ?? []).map((event) => (
                <BridgeEventRow key={event.id} event={event} />
              ))}
            </div>
          </section>
        </div>
      </main>
    </div>
  )
}

function ConversationListItem({
  conversation,
  active,
  onClick,
}: {
  conversation: BridgeConversationSummary
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className={cn(
        'w-full rounded-2xl border p-3 text-left transition',
        active
          ? 'border-blue-200 bg-blue-50 shadow-sm'
          : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50',
      )}
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="mono text-xs text-slate-500">
            {conversation.adapter} · {conversation.tenant_key}
          </p>
          <p className="mt-1 truncate text-sm font-semibold text-slate-900">
            {conversation.external_chat_id}
          </p>
        </div>
        {conversation.latest_event_status ? (
          <StatusBadge status={conversation.latest_event_status} />
        ) : null}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500">
        <span>Events {conversation.event_count}</span>
        <span>Profile {conversation.profile_name ?? 'default'}</span>
        <span className="mono">
          Session {formatShortId(conversation.session_id)}
        </span>
        <span className="mono">
          Active {formatShortId(conversation.active_run_id)}
        </span>
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Last event {formatDate(conversation.last_event_at)}
      </p>
    </button>
  )
}

function BridgeMetrics({
  conversations,
  events,
}: {
  conversations: BridgeConversationSummary[]
  events: BridgeEventSummary[]
}) {
  const steered = events.filter((event) => event.status === 'steered').length
  const failed = events.filter((event) => event.status === 'failed').length
  const delivered = events.filter((event) =>
    ['queued', 'submitted', 'steered'].includes(event.status),
  ).length
  return (
    <div className="grid grid-cols-4 gap-4">
      <MetricCard
        icon={MessageSquare}
        label="Conversations"
        value={String(conversations.length)}
        accent="blue"
      />
      <MetricCard
        icon={Send}
        label="Delivered"
        value={String(delivered)}
        accent="emerald"
      />
      <MetricCard
        icon={Route}
        label="Steered"
        value={String(steered)}
        accent="amber"
      />
      <MetricCard
        icon={Bot}
        label="Failed"
        value={String(failed)}
        accent="rose"
      />
    </div>
  )
}

function ConversationDetail({
  conversation,
}: {
  conversation: BridgeConversationSummary | null
}) {
  const selectSession = useLayoutStore((state) => state.selectSession)
  const selectRun = useLayoutStore((state) => state.selectRun)
  if (!conversation) {
    return (
      <EmptyState
        title="Select a bridge conversation"
        description="Conversation mapping, session ID, active run, and metadata appear here."
      />
    )
  }
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-blue-600">
            Conversation record
          </p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">
            {conversation.external_chat_id}
          </h2>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition hover:bg-slate-50"
            onClick={() => selectSession(conversation.session_id)}
          >
            Open session
          </button>
          {conversation.active_run_id ? (
            <button
              type="button"
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition hover:bg-slate-50"
              onClick={() => selectRun(conversation.active_run_id ?? null)}
            >
              Open active run
            </button>
          ) : null}
        </div>
      </div>
      <dl className="mt-5 grid grid-cols-3 gap-4 text-sm">
        <Detail label="Adapter" value={conversation.adapter} />
        <Detail label="Tenant" value={conversation.tenant_key} />
        <Detail
          label="Profile"
          value={conversation.profile_name ?? 'default'}
        />
        <Detail label="Session" value={conversation.session_id} mono />
        <Detail
          label="Active run"
          value={conversation.active_run_id ?? 'none'}
          mono
        />
        <Detail
          label="Last event"
          value={formatDate(conversation.last_event_at)}
        />
      </dl>
      <div className="mt-5">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
          Metadata
        </p>
        <JsonView value={conversation.metadata} height="180px" />
      </div>
    </section>
  )
}

function BridgeEventRow({ event }: { event: BridgeEventSummary }) {
  const [expanded, setExpanded] = useState(false)
  const selectSession = useLayoutStore((state) => state.selectSession)
  const selectRun = useLayoutStore((state) => state.selectRun)
  return (
    <article className="rounded-xl border border-slate-100 p-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="mono text-xs text-slate-500">
            {formatShortId(event.id, 12)} · {event.event_type}
          </p>
          <p className="mt-1 truncate font-medium text-slate-900">
            {event.external_message_id ?? event.event_id}
          </p>
        </div>
        <StatusBadge status={mapEventStatus(event.status, event.run_status)} />
      </div>
      <div className="mt-3 grid grid-cols-4 gap-2 text-xs text-slate-500">
        <span className="mono">
          Chat {formatShortId(event.external_chat_id)}
        </span>
        <span className="mono">Session {formatShortId(event.session_id)}</span>
        <span className="mono">Run {formatShortId(event.run_id)}</span>
        <span>{formatDate(event.created_at)}</span>
      </div>
      {event.error_message ? (
        <p className="mt-2 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {event.error_message}
        </p>
      ) : null}
      <div className="mt-3 flex items-center gap-2">
        {event.session_id ? (
          <button
            type="button"
            className="rounded-lg border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
            onClick={() => selectSession(event.session_id ?? null)}
          >
            Open session
          </button>
        ) : null}
        {event.run_id ? (
          <button
            type="button"
            className="rounded-lg border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
            onClick={() => selectRun(event.run_id ?? null)}
          >
            Open run
          </button>
        ) : null}
        <button
          type="button"
          className="rounded-lg border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? 'Hide payload' : 'Show payload'}
        </button>
      </div>
      {expanded ? (
        <div className="mt-3 grid grid-cols-2 gap-3">
          <JsonView value={event.normalized_event} height="240px" />
          <JsonView value={event.raw_event} height="240px" />
        </div>
      ) : null}
    </article>
  )
}

const metricAccentClasses: Record<string, string> = {
  blue: 'bg-blue-50 text-blue-600',
  emerald: 'bg-emerald-50 text-emerald-600',
  amber: 'bg-amber-50 text-amber-600',
  rose: 'bg-rose-50 text-rose-600',
}

function MetricCard({
  icon: Icon,
  label,
  value,
  accent,
}: {
  icon: typeof MessageSquare
  label: string
  value: string
  accent: string
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div
        className={`inline-flex rounded-xl p-2 ${metricAccentClasses[accent] ?? metricAccentClasses.blue}`}
      >
        <Icon className="h-5 w-5" />
      </div>
      <p className="mt-4 text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-950">{value}</p>
    </div>
  )
}

function Detail({
  label,
  value,
  mono,
}: {
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </dt>
      <dd className={cn('mt-1 break-all text-slate-800', mono && 'mono')}>
        {value}
      </dd>
    </div>
  )
}

function ConversationSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 5 }).map((_, index) => (
        <div
          key={index}
          className="h-32 animate-pulse rounded-2xl bg-slate-100"
        />
      ))}
    </div>
  )
}

function EventSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 4 }).map((_, index) => (
        <div
          key={index}
          className="h-24 animate-pulse rounded-xl bg-slate-100"
        />
      ))}
    </div>
  )
}

function formatDate(value?: string | null) {
  if (!value) return 'none'
  return new Date(value).toLocaleString()
}

function mapEventStatus(status: BridgeEventStatus, runStatus?: string | null) {
  if (status === 'failed') return 'failed'
  if (runStatus === 'completed') return 'completed'
  if (runStatus === 'failed') return 'failed'
  if (runStatus === 'cancelled') return 'cancelled'
  if (status === 'queued' || status === 'submitted' || status === 'steered') {
    return 'running'
  }
  return status
}
