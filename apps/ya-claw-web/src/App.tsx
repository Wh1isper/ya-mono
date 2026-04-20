import { useEffect, useMemo, useState } from 'react'

type ClawInfo = {
  name: string
  environment: string
  public_base_url: string
  surfaces: string[]
  provider_model: string
  storage_model: string
}

const productTracks = [
  {
    title: 'Workspaces',
    description:
      'Resolve local workspaces and projects through one configured WorkspaceProvider.',
  },
  {
    title: 'Profiles',
    description:
      'Reuse agent defaults for model, prompt, toolsets, and workspace-aware execution hints.',
  },
  {
    title: 'Sessions and Runs',
    description:
      'Keep committed runtime state in SQLite by default, track active work in process memory, and stream live output to connected clients.',
  },
]

function App() {
  const baseUrl = useMemo(
    () => import.meta.env.VITE_CLAW_BASE_URL ?? 'http://127.0.0.1:9042',
    [],
  )
  const [info, setInfo] = useState<ClawInfo | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void fetch(`${baseUrl}/api/v1/claw/info`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`request failed with ${response.status}`)
        }
        return response.json() as Promise<ClawInfo>
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
        <p className="eyebrow">Workspace-native single-node runtime</p>
        <h1>YA Claw</h1>
        <p className="hero-copy">
          A local-first runtime shell for ya-agent-sdk with WorkspaceProvider,
          in-process runtime state, SQLite-first storage, and a bundled web UI.
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
            <h2>Runtime status</h2>
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
              <span className="label">Provider model</span>
              <strong>{info.provider_model}</strong>
            </div>
            <div>
              <span className="label">Storage model</span>
              <strong>{info.storage_model}</strong>
            </div>
          </div>
        ) : (
          <div className="status-empty">
            <strong>
              {error ? 'Backend unavailable' : 'Waiting for backend response'}
            </strong>
            <p>
              {error ??
                'Start the backend with `uv run --package ya-claw ya-claw serve --reload`.'}
            </p>
          </div>
        )}
      </section>
    </main>
  )
}

export default App
