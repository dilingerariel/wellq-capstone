import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { apiSource, type ClinicalSource } from '../services/clinical'
import type { PortalSession, Role } from '../types/session'
import { SessionManager, type SessionPhase } from '../services/session'
import { Connectivity, type ConnectionStatus } from '../services/connectivity'
import { ReadRecovery } from '../services/synchronization'

const mode = import.meta.env.VITE_DATA_MODE || 'demo'
if (mode !== 'demo' && mode !== 'api') throw new Error('VITE_DATA_MODE must be demo or api')
interface Runtime {
  mode: 'demo' | 'api'
  role: Role
  session: PortalSession | null
  source: ClinicalSource | null
  loading: boolean
  sessionPhase: SessionPhase
  boundary: number
  connection: ConnectionStatus
  canRequest: boolean
  setDemoRole: (role: Role) => void
  reloadIdentity: () => void
  signIn: () => void
  signOut: () => void
  checkConnection: () => void
  canSignIn: boolean
  canRenew: boolean
}
const Context = createContext<Runtime | null>(null)
export function RuntimeProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<Role>('clinician')
  const [demo, setDemo] = useState<ClinicalSource | null>(null)
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: false,
            networkMode: 'always',
            staleTime: 30_000,
            gcTime: 600_000,
            refetchOnWindowFocus: false,
            refetchOnReconnect: false,
            refetchOnMount: false,
          },
        },
      }),
  )
  const [manager] = useState(
    () =>
      new SessionManager(
        () => window.wellqIdentity,
        () => {
          void client.cancelQueries()
          client.clear()
        },
      ),
  )
  const [network] = useState(
    () =>
      new Connectivity(
        mode === 'api'
          ? import.meta.env.VITE_API_HEALTH_URL ||
              new URL(
                '/health',
                new URL(import.meta.env.VITE_API_BASE_URL || '/api/v1', window.location.origin),
              ).href
          : null,
      ),
  )
  const [recovery] = useState(() => new ReadRecovery())
  const identity = useSyncExternalStore(manager.subscribe, manager.getSnapshot)
  const connectionState = useSyncExternalStore(network.subscribe, network.getSnapshot)
  const connection = connectionState.status
  const [approvedRecovery, setApprovedRecovery] = useState(0)
  const renewedExpiry = useRef<number | null>(null)
  useEffect(() => network.start(), [network])
  useEffect(() => {
    if (mode === 'api') return manager.connect()
    let active = true
    void import('../features/demo/source').then((m) => {
      if (active) setDemo(m.demoSource)
    })
    return () => {
      active = false
    }
  }, [manager])
  useEffect(() => {
    if (mode !== 'api' || connection !== 'online' || connectionState.recovery === approvedRecovery)
      return
    const version = connectionState.recovery
    void recovery.run(`reconnect:${version}`, async () => {
      // Mark stale without dispatching reads before fresh identity/permissions are available.
      await client.invalidateQueries({ refetchType: 'none' })
      const valid = await manager.verify(true)
      if (valid && version === network.getSnapshot().recovery) setApprovedRecovery(version)
    })
  }, [connection, connectionState.recovery, approvedRecovery, manager, client, recovery, network])
  useEffect(() => {
    const session = identity.session
    if (!session) return
    const expires = window.setTimeout(
      () => manager.invalidate(session.accessToken, 'expired'),
      Math.min(Math.max(0, session.expiresAt * 1000 - Date.now()), 2147483647),
    )
    const renew = window.setTimeout(
      () => {
        if (
          connection === 'online' &&
          window.wellqIdentity?.refreshSession &&
          renewedExpiry.current !== session.expiresAt
        ) {
          renewedExpiry.current = session.expiresAt
          void manager.verify(true)
        }
      },
      Math.min(Math.max(0, session.expiresAt * 1000 - Date.now() - 60_000), 2147483647),
    )
    return () => {
      window.clearTimeout(expires)
      window.clearTimeout(renew)
    }
  }, [identity.session, manager, connection])
  useEffect(
    () => () => {
      void client.cancelQueries()
      client.clear()
    },
    [client],
  )
  const source = useMemo(
    () =>
      mode === 'demo'
        ? demo
        : identity.session
          ? apiSource(
              import.meta.env.VITE_API_BASE_URL || '/api/v1',
              identity.session.role,
              () => manager.getSnapshot().session?.accessToken,
              (token) => manager.invalidate(token),
              (status) => network.report(status),
            )
          : null,
    [demo, identity.session, manager, network],
  )
  const setDemoRole = useCallback(
    (next: Role) => {
      if (mode === 'demo') {
        void client.cancelQueries()
        client.clear()
        setRole(next)
      }
    },
    [client],
  )
  return (
    <Context.Provider
      value={{
        mode,
        role: identity.session?.role || role,
        session: identity.session,
        source,
        loading: identity.phase === 'loading',
        sessionPhase: identity.phase,
        boundary: identity.boundary,
        connection,
        canRequest:
          mode === 'demo' ||
          (identity.phase === 'authenticated' &&
            connection === 'online' &&
            approvedRecovery === connectionState.recovery),
        setDemoRole,
        reloadIdentity: () => {
          void manager.verify(true, true).then((valid) => {
            if (valid) setApprovedRecovery(network.getSnapshot().recovery)
          })
        },
        signIn: () => {
          void manager.signIn().then((valid) => {
            if (valid) setApprovedRecovery(network.getSnapshot().recovery)
          })
        },
        signOut: () => {
          void manager.signOut()
        },
        checkConnection: () => {
          void network.check()
        },
        canSignIn: Boolean(window.wellqIdentity?.signIn),
        canRenew: Boolean(window.wellqIdentity?.refreshSession),
      }}
    >
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </Context.Provider>
  )
}
export function useRuntime() {
  const value = useContext(Context)
  if (!value) throw new Error('Runtime missing')
  return value
}
