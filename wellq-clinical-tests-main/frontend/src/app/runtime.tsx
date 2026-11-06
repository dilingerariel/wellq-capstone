import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { apiSource, type ClinicalSource } from '../services/clinical'
import { sessionSchema, type PortalSession, type Role } from '../types/session'
import { ApiError } from '../services/http'

const mode = import.meta.env.VITE_DATA_MODE || 'demo'
if (mode !== 'demo' && mode !== 'api') throw new Error('VITE_DATA_MODE must be demo or api')
interface Runtime {
  mode: 'demo' | 'api'
  role: Role
  session: PortalSession | null
  source: ClinicalSource | null
  loading: boolean
  setDemoRole: (role: Role) => void
  reloadIdentity: () => void
}
const Context = createContext<Runtime | null>(null)
export function RuntimeProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<Role>('clinician')
  const [session, setSession] = useState<PortalSession | null>(null)
  const [loading, setLoading] = useState(mode === 'api')
  const [demo, setDemo] = useState<ClinicalSource | null>(null)
  const [revision, setRevision] = useState(0)
  const invalidate = useCallback(() => {
    setSession(null)
  }, [])
  const reloadIdentity = useCallback(() => {
    setRevision((v) => v + 1)
  }, [])
  useEffect(() => {
    if (mode !== 'demo') return
    let active = true
    void import('../features/demo/source').then((m) => {
      if (active) setDemo(m.demoSource)
    })
    return () => {
      active = false
    }
  }, [])
  useEffect(() => {
    if (mode !== 'api') return
    let active = true
    let generation = 0
    const load = async () => {
      const request = ++generation
      setSession(null)
      setLoading(true)
      try {
        const result = sessionSchema.safeParse(await window.wellqIdentity?.getSession())
        if (
          active &&
          request === generation &&
          result.success &&
          result.data.expiresAt * 1000 > Date.now()
        )
          setSession(result.data)
      } catch {
        if (active && request === generation) setSession(null)
      } finally {
        if (active && request === generation) setLoading(false)
      }
    }
    // Provider failures close the session; never switch to demo.
    void load()
    const unsubscribe = window.wellqIdentity?.subscribe?.(() => {
      invalidate()
      void load()
    })
    return () => {
      active = false
      unsubscribe?.()
    }
  }, [revision, invalidate])
  useEffect(() => {
    if (!session) return
    const timer = window.setTimeout(
      invalidate,
      Math.min(session.expiresAt * 1000 - Date.now(), 2147483647),
    )
    return () => window.clearTimeout(timer)
  }, [session, invalidate])
  const actualRole = session?.role || role
  const client = useMemo(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            enabled: Boolean(session) || mode === 'demo',
            meta: { role, revision },
            retry: (count, error) =>
              !(
                error instanceof ApiError &&
                [401, 403, 404, 409, 422, 429, 503].includes(error.status)
              ) && count < 1,
            staleTime: 15_000,
            gcTime: 0,
            refetchOnWindowFocus: false,
          },
        },
      }),
    [session, role, revision],
  )
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
        : session
          ? apiSource(
              import.meta.env.VITE_API_BASE_URL || '/api/v1',
              session.role,
              () => session.accessToken,
              invalidate,
            )
          : null,
    [demo, session, invalidate],
  )
  return (
    <Context.Provider
      value={{
        mode,
        role: actualRole,
        session,
        source,
        loading,
        setDemoRole: setRole,
        reloadIdentity,
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
