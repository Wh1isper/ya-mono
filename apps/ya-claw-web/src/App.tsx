import { AppShell } from './app/AppShell'
import { ConnectionGate } from './app/ConnectionGate'
import { Providers } from './app/Providers'

function App() {
  return (
    <Providers>
      <ConnectionGate>
        <AppShell />
      </ConnectionGate>
    </Providers>
  )
}

export default App
