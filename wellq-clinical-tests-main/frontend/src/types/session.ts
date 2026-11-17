import { z } from 'zod'

export const sessionSchema = z.object({
  accessToken: z.string().min(1),
  role: z.enum(['patient', 'clinician']),
  resourceId: z.string().min(1).max(200),
  tenantId: z.string().min(1),
  permissions: z.array(z.string()),
  capabilities: z.array(z.string()),
  expiresAt: z.number().int().positive(),
})
export type PortalSession = z.infer<typeof sessionSchema>
export type Role = PortalSession['role']
export interface IdentityProvider {
  demoLogin?: boolean
  getSession: () => Promise<unknown>
  signIn?: () => Promise<void>
  signOut?: () => Promise<void>
  refreshSession?: () => Promise<unknown>
  subscribe?: (callback: () => void) => () => void
}
declare global {
  interface Window {
    /** Supplied by the trusted identity host, before mounting React. No login endpoint is invented. */
    wellqIdentity?: IdentityProvider
    wellqDemoSelection?: {
      role?: Role
      clientId?: string
      clinicianId?: string
      patientId?: string
    }
  }
}
