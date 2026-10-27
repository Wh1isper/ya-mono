import type { AguiEvent } from '../../types'

// Own compact event shells; published snapshots remain immutable while new
// chunks replace only their matching entry. Never truncate canonical text.
export class LiveReplay {
  private events: AguiEvent[] = []
  private chunks = new Map<string, number>()

  append(event: AguiEvent) {
    if (event.type === 'RUN_STARTED') this.chunks.clear()
    const id =
      event.type === 'TOOL_CALL_CHUNK'
        ? (event.toolCallKey ??
          event.tool_call_key ??
          event.toolCallId ??
          event.tool_call_id)
        : event.type === 'TEXT_MESSAGE_CHUNK' ||
            event.type === 'REASONING_MESSAGE_CHUNK'
          ? (event.messageId ?? event.message_id)
          : undefined
    const key = id ? `${event.type}:${id}` : null
    const index = key ? this.chunks.get(key) : undefined
    if (index !== undefined) {
      const previous = this.events[index]
      this.events[index] = {
        ...previous,
        ...event,
        delta: `${previous.delta ?? ''}${event.delta ?? ''}`,
      }
    } else {
      if (key) this.chunks.set(key, this.events.length)
      this.events.push(event)
    }
  }

  replace(events: AguiEvent[]) {
    this.events = []
    this.chunks.clear()
    for (const event of events) this.append(event)
  }

  snapshot(): AguiEvent[] {
    return this.events.slice()
  }
}
