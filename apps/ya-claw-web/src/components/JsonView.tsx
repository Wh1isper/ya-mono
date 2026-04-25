import { safeJsonStringify } from '../lib/utils'

export function JsonView({
  value,
  height = '240px',
}: {
  value: unknown
  height?: string
}) {
  return (
    <pre
      className="scrollbar-thin overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs leading-5 text-slate-800"
      style={{ maxHeight: height }}
    >
      {safeJsonStringify(value)}
    </pre>
  )
}
