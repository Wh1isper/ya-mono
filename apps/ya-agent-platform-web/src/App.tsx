import { useEffect, useMemo, useState } from 'react'

type PlatformInfo = {
  name: string
  environment: string
  public_base_url: string
  surfaces: string[]
  bridge_model: string
  runtime_model: string
}

const productTracks = [
  {
    title: 'Management Portal',
    description:
      'Workspace, agent profile, bridge, credential, and policy operations.',
  },
  {
    title: 'Chat UI',
    description:
      'First-party browser chat that talks to the same session model as IM bridges.',
  },
  {
    title: 'IM Bridges',
    description:
      'Normalized adapters for Discord, Telegram, Slack, WeCom, email, and future channels.',
  },
]

function App() {
  const baseUrl = useMemo(
    () => import.meta.env.VITE_PLATFORM_BASE_URL ?? 'http://127.0.0.1:9042',
    [],
  )
  const [info, setInfo] = useState<PlatformInfo | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void fetch(`${baseUrl}/api/v1/platform/info`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`request failed with ${response.status}`)
        }
        return response.json() as Promise<PlatformInfo>
      })
      .then(setInfo)
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : 'unknown error'
        setError(message)
      })
  }, [baseUrl])

  return (
    <main className="page-shell">
      <section className="hero">
        <p className="eyebrow">Cloud-ready agent platform</p>
        <h1>YA Agent Platform</h1>
        <p className="hero-copy">
          A unified platform for operator administration, browser chat, and IM
          bridge delivery on top of ya-agent-sdk.
        </p>
      </section>

      <section className="panel-grid">
        {productTracks.map((track) => (
          <article className="panel" key={track.title}>
            <h2>{track.title}</h2>
            <p>{track.description}</p>
          </article>
        ))}
      </section>

      <section className="platform-status panel panel-wide">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Backend handshake</p>
            <h2>Platform status</h2>
          </div>
          <code>{baseUrl}</code>
        </div>

        {info ? (
          <div className="status-grid">
            <div>
              <span className="label">Name</span>
              <strong>{info.name}</strong>
            </div>
            <div>
              <span className="label">Environment</span>
              <strong>{info.environment}</strong>
            </div>
            <div>
              <span className="label">Public base URL</span>
              <strong>{info.public_base_url}</strong>
            </div>
            <div>
              <span className="label">Surfaces</span>
              <strong>{info.surfaces.join(', ')}</strong>
            </div>
            <div>
              <span className="label">Bridge model</span>
              <strong>{info.bridge_model}</strong>
            </div>
            <div>
              <span className="label">Runtime model</span>
              <strong>{info.runtime_model}</strong>
            </div>
          </div>
        ) : (
          <div className="status-empty">
            <strong>
              {error ? 'Backend unavailable' : 'Waiting for backend response'}
            </strong>
            <p>
              {error ??
                'Start the backend with `uv run --package ya-agent-platform ya-agent-platform serve --reload`.'}
            </p>
          </div>
        )}
      </section>
    </main>
  )
}

export default App
