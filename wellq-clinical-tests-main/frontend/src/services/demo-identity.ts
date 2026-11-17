import type { IdentityProvider, PortalSession } from '../types/session'

let currentSession: PortalSession | null = null

const listeners = new Set<() => void>()
const notify = () => listeners.forEach((fn) => fn())

export const demoIdentity: IdentityProvider = {
  demoLogin: true,
  getSession: async () => {
    if (currentSession && currentSession.expiresAt * 1000 > Date.now()) {
      return currentSession
    }
    return null
  },
  refreshSession: async () => {
    if (currentSession && currentSession.expiresAt * 1000 > Date.now()) {
      return currentSession
    }
    return null
  },
  signIn: async (params?: {
    role?: 'clinician' | 'patient'
    clientId?: string
    clinicianId?: string
    patientId?: string
  }) => {
    const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    const selection = params || window.wellqDemoSelection || {}
    const isPatientPath =
      typeof window !== 'undefined' &&
      (/^\/(patient|upload)(\/|$)/.test(window.location.pathname) ||
        window.location.pathname.endsWith('/extraction'))

    const role = selection.role || (isPatientPath ? 'patient' : 'clinician')
    const clientId = selection.clientId || 'clinica_alemana'
    const clinicianId = selection.clinicianId || 'rene_faundez'
    const patientId = selection.patientId || 'paciente_ariel_demo'

    const response = await fetch(`${apiBase}/demo/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        role,
        client_id: clientId,
        clinician_id: clinicianId,
        patient_id: patientId,
      }),
    })

    if (!response.ok) {
      throw new Error(`Demo login failed with status ${response.status}`)
    }

    const data = (await response.json()) as PortalSession
    currentSession = data
    notify()
  },
  signOut: async () => {
    currentSession = null
    notify()
  },
  subscribe: (fn) => {
    listeners.add(fn)
    return () => listeners.delete(fn)
  },
}

export function initDemoIdentity() {
  if (typeof window !== 'undefined' && !window.wellqIdentity) {
    window.wellqIdentity = demoIdentity
  }
}
