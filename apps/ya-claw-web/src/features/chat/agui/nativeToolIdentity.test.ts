import { describe, expect, it } from 'vitest'
import { LiveReplay } from '../liveReplay'
import { buildTimelineFromRuns } from './eventReducer'

// Provider IDs are data; the adapter-owned key identifies a displayed invocation.
describe('native tool identities', () => {
  it('keeps calls across agents, segments, and runs separate', () => {
    const call = (key: string, name: string) => [
      {
        type: 'TOOL_CALL_START',
        toolCallId: 'same',
        toolCallKey: key,
        toolCallName: name,
      },
      {
        type: 'TOOL_CALL_CHUNK',
        toolCallId: 'same',
        toolCallKey: key,
        delta: '{"x":1}',
      },
      {
        type: 'TOOL_CALL_RESULT',
        toolCallId: 'same',
        toolCallKey: key,
        content: `${name} done`,
      },
    ]
    const state = buildTimelineFromRuns([
      {
        id: 'run1',
        message: [
          ...call('run1:tool:1', 'root'),
          ...call('run1:tool:2', 'child'),
          ...call('run1:tool:3', 'root again'),
        ],
      },
      { id: 'run2', message: call('run2:tool:1', 'next run') },
    ])
    const calls = state.blocks.filter((block) => block.kind === 'tool_call')
    expect(calls).toHaveLength(4)
    expect(new Set(calls.map((block) => block.id)).size).toBe(4)
    expect(calls.map((block) => block.toolCallId)).toEqual([
      'same',
      'same',
      'same',
      'same',
    ])
    expect(calls.map((block) => block.args)).toEqual(Array(4).fill('{"x":1}'))
    expect(calls.map((block) => block.result)).toEqual([
      'root done',
      'child done',
      'root again done',
      'next run done',
    ])
  })

  it('coalesces live and snapshot chunks by display invocation', () => {
    const replay = new LiveReplay()
    const chunk = (key: string, delta: string) => ({
      type: 'TOOL_CALL_CHUNK',
      toolCallId: 'same',
      toolCallKey: key,
      delta,
    })
    replay.append(chunk('run:tool:1', '{"x":'))
    replay.append(chunk('run:tool:2', '{"y":'))
    const earlier = replay.snapshot()
    replay.replace(earlier)
    replay.append(chunk('run:tool:1', '1}'))
    replay.append(chunk('run:tool:2', '2}'))
    expect(earlier.map((event) => event.delta)).toEqual(['{"x":', '{"y":'])
    const state = buildTimelineFromRuns([
      { id: 'run', message: replay.snapshot() },
    ])
    expect(state.blocks).toMatchObject([
      {
        kind: 'tool_call',
        id: 'tool:run:tool:1',
        toolCallId: 'same',
        args: '{"x":1}',
      },
      {
        kind: 'tool_call',
        id: 'tool:run:tool:2',
        toolCallId: 'same',
        args: '{"y":2}',
      },
    ])
  })

  it('retains a start-only observed call', () => {
    const state = buildTimelineFromRuns([
      {
        id: 'run',
        message: [
          {
            type: 'TOOL_CALL_START',
            toolCallId: 'native',
            toolCallKey: 'run:tool:1',
            toolCallName: 'lookup',
          },
        ],
      },
    ])
    expect(state.blocks).toMatchObject([
      {
        kind: 'tool_call',
        toolCallId: 'native',
        name: 'lookup',
        status: 'calling',
      },
    ])
  })
})
