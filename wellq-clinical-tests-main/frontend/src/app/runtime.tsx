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
import type { LoginInput, PatientRegistrationInput, PortalSession, Role } from '../types/session'
import { SessionManager, type SessionPhase } from '../services/session'
import { Connectivity, type ConnectionStatus } from '../services/connectivity'
import { ReadRecovery, recoverInvalidatedReads } from '../services/synchronization'
import { UploadController } from '../features/uploads/controller'
import { uploadApi } from '../features/uploads/api'
import { createHttp } from '../services/http'
import { ReviewController } from '../features/review/controller'
import { reviewApi } from '../features/review/model'
import { ClinicianController } from '../features/clinician/controller'
import { clinicianApi } from '../features/clinician/model'
import { reportingApi, type ReportingApi } from '../features/records/model'
import { ReportExportController } from '../features/records/export-controller'
import { resolveDataMode } from './data-mode'

const mode = resolveDataMode(import.meta.env.VITE_DATA_MODE, import.meta.env.PROD)
interface Runtime {
  pdfExportEnabled: boolean
  reporting: ReportingApi
  reportExport: ReportExportController
  verifySession: () => Promise<boolean>
  clinician: ClinicianController
  review: ReviewController
  upload: UploadController
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
  signIn: (input?: LoginInput) => Promise<boolean>
  registerPatient: (input: PatientRegistrationInput) => Promise<boolean>
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
  const [privateResources] = useState(() => new Set<() => void>())
  const [manager] = useState(
    () =>
      new SessionManager(
        () => window.wellqIdentity,
        () => {
          privateResources.forEach((clear) => clear())
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
  const [approval] = useState(() => ({ version: 0 }))
  const [reporting] = useState(() =>
    reportingApi(
      createHttp(
        import.meta.env.VITE_API_BASE_URL || '/api/v1',
        () => manager.getSnapshot().session?.accessToken,
        (token) => manager.invalidate(token),
        (status) => {
          if (status === 'unavailable') window.setTimeout(() => network.report(status), 0)
          else network.report(status)
        },
      ),
    ),
  )
  const [reportExport] = useState(
    () =>
      new ReportExportController(
        reporting,
        () => {
          const current = manager.getSnapshot(),
            net = network.getSnapshot(),
            s = current.session
          return (
            import.meta.env.DEV &&
            mode === 'api' &&
            current.phase === 'authenticated' &&
            s?.role === 'clinician' &&
            s.expiresAt * 1000 > Date.now() &&
            ['clinical:read', 'reports:export'].every((p) => s.permissions.includes(p)) &&
            s.capabilities.includes('report_export') &&
            net.status === 'online' &&
            approval.version === net.recovery
          )
        },
        async () => {
          const boundary = manager.getSnapshot().boundary
          return (await manager.verify(true)) && boundary === manager.getSnapshot().boundary
        },
      ),
  )
  const [upload] = useState(
    () =>
      new UploadController(
        uploadApi(
          createHttp(
            import.meta.env.VITE_API_BASE_URL || '/api/v1',
            () => manager.getSnapshot().session?.accessToken,
            (token) => manager.invalidate(token),
            (status) => {
              // Let the upload retain the received HTTP error/Retry-After before
              // connectivity effects suspend further work on this operation.
              if (status === 'unavailable') window.setTimeout(() => network.report(status), 0)
              else network.report(status)
            },
          ),
        ),
        () => {
          const current = manager.getSnapshot(),
            connection = network.getSnapshot()
          return (
            mode === 'api' &&
            current.phase === 'authenticated' &&
            current.session?.role === 'patient' &&
            current.session.expiresAt * 1000 > Date.now() &&
            ['clinical:read', 'clinical:write'].every((permission) =>
              current.session?.permissions.includes(permission),
            ) &&
            connection.status === 'online' &&
            approval.version === connection.recovery
          )
        },
      ),
  )
  const [review] = useState(
    () =>
      new ReviewController(
        reviewApi(
          createHttp(
            import.meta.env.VITE_API_BASE_URL || '/api/v1',
            () => manager.getSnapshot().session?.accessToken,
            (token) => manager.invalidate(token),
            (status) => {
              if (status === 'unavailable') window.setTimeout(() => network.report(status), 0)
              else network.report(status)
            },
          ),
        ),
        () => {
          const current = manager.getSnapshot(),
            net = network.getSnapshot()
          return {
            patient: current.session?.resourceId || '',
            allowed:
              mode === 'api' &&
              current.phase === 'authenticated' &&
              current.session?.role === 'patient' &&
              current.session.expiresAt * 1000 > Date.now() &&
              current.session.permissions.includes('clinical:read') &&
              net.status === 'online' &&
              approval.version === net.recovery,
            confirm: !!current.session?.permissions.includes('extractions:confirm'),
          }
        },
        () => manager.verify(true),
      ),
  )
  const [clinician] = useState(
    () =>
      new ClinicianController(
        clinicianApi(
          createHttp(
            import.meta.env.VITE_API_BASE_URL || '/api/v1',
            () => manager.getSnapshot().session?.accessToken,
            (token) => manager.invalidate(token),
            (status) => {
              if (status === 'unavailable') window.setTimeout(() => network.report(status), 0)
              else network.report(status)
            },
          ),
        ),
        () => {
          const current = manager.getSnapshot(),
            net = network.getSnapshot()
          return {
            allowed:
              mode === 'api' &&
              current.phase === 'authenticated' &&
              current.session?.role === 'clinician' &&
              current.session.expiresAt * 1000 > Date.now() &&
              current.session.permissions.includes('clinical:read') &&
              net.status === 'online' &&
              approval.version === net.recovery,
            clinician: current.session?.resourceId || '',
            permissions: current.session?.permissions || [],
          }
        },
        () => manager.verify(true),
        () => {
          void client.resetQueries({
            predicate: (q) => ['exam', 'exams'].includes(String(q.queryKey[0])),
          })
        },
      ),
  )
  useEffect(() => {
    privateResources.add(reportExport.clear)
    privateResources.add(clinician.clear)
    privateResources.add(review.clear)
    privateResources.add(upload.clear)
    return () => {
      privateResources.delete(reportExport.clear)
      reportExport.clear()
      privateResources.delete(upload.clear)
      privateResources.delete(review.clear)
      privateResources.delete(clinician.clear)
      clinician.clear()
      review.clear()
      upload.clear()
    }
  }, [privateResources, upload, review, clinician, reportExport])
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
      if (valid && version === network.getSnapshot().recovery) {
        approval.version = version
        setApprovedRecovery(version)
      }
    })
  }, [
    connection,
    connectionState.recovery,
    approvedRecovery,
    manager,
    client,
    recovery,
    network,
    approval,
  ])
  useEffect(() => {
    if (
      connection !== 'online' ||
      identity.phase !== 'authenticated' ||
      approvedRecovery !== connectionState.recovery
    ) {
      upload.suspend()
      if (identity.phase !== 'loading' || connection !== 'online') {
        review.suspend()
        clinician.suspend()
        reportExport.suspend()
      }
    }
  }, [
    connection,
    identity.phase,
    approvedRecovery,
    connectionState.recovery,
    upload,
    review,
    clinician,
    reportExport,
  ])
  useEffect(() => {
    if (
      mode !== 'api' ||
      connection !== 'online' ||
      identity.phase !== 'authenticated' ||
      !approvedRecovery ||
      approvedRecovery !== connectionState.recovery
    )
      return
    const version = approvedRecovery,
      boundary = identity.boundary,
      token = identity.session?.accessToken
    return recoverInvalidatedReads(client, () => {
      const current = manager.getSnapshot(),
        net = network.getSnapshot()
      return (
        current.phase === 'authenticated' &&
        current.boundary === boundary &&
        current.session?.accessToken === token &&
        net.status === 'online' &&
        net.recovery === version &&
        approval.version === version
      )
    })
  }, [
    connection,
    identity.phase,
    identity.boundary,
    identity.session?.accessToken,
    approvedRecovery,
    connectionState.recovery,
    manager,
    network,
    client,
    approval,
  ])
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
        upload.clear()
        void client.cancelQueries()
        client.clear()
        setRole(next)
      }
    },
    [client, upload],
  )
  return (
    <Context.Provider
      value={{
        pdfExportEnabled: import.meta.env.DEV,
        reporting,
        reportExport,
        verifySession: async () => {
          const before = manager.getSnapshot().boundary
          return (await manager.verify(true)) && before === manager.getSnapshot().boundary
        },
        clinician,
        review,
        upload,
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
            if (valid) {
              approval.version = network.getSnapshot().recovery
              setApprovedRecovery(approval.version)
            }
          })
        },
        signIn: (input) => {
          const operation = manager.signIn(input)
          void operation.then((valid) => {
            if (valid) {
              approval.version = network.getSnapshot().recovery
              setApprovedRecovery(approval.version)
            }
          })
          return operation
        },
        registerPatient: (input) => {
          const operation = manager.registerPatient(input)
          void operation.then((valid) => {
            if (valid) {
              approval.version = network.getSnapshot().recovery
              setApprovedRecovery(approval.version)
            }
          })
          return operation
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
