export const queryKeys = {
  health: ['health'] as const,
  clawInfo: ['claw-info'] as const,
  sessions: ['sessions'] as const,
  session: (sessionId: string) => ['session', sessionId] as const,
  run: (runId: string) => ['run', runId] as const,
  runTrace: (runId: string) => ['run-trace', runId] as const,
  profiles: ['profiles'] as const,
  profile: (profileName: string) => ['profile', profileName] as const,
}
