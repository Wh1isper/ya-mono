import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatShortId(value: string | null | undefined, length = 8) {
  if (!value) return 'none'
  return value.length <= length ? value : value.slice(0, length)
}

export function safeJsonStringify(value: unknown, space = 2) {
  try {
    return JSON.stringify(value, null, space)
  } catch {
    return String(value)
  }
}

export function splitCsv(value: string) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

export function joinCsv(values: string[] | null | undefined) {
  return (values ?? []).join(', ')
}

export function parseJsonObject(value: string): Record<string, unknown> | null {
  const normalized = value.trim()
  if (!normalized) return null
  const parsed = JSON.parse(normalized) as unknown
  if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error('Expected a JSON object')
  }
  return parsed as Record<string, unknown>
}
