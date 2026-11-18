import { z } from 'zod'

export const sessionSchema = z.object({
  accessToken: z.string().min(1),
  role: z.enum(['patient', 'clinician']),
  resourceId: z.string().min(1).max(200),
  tenantId: z.string().min(1),
  permissions: z.array(z.string()),
  capabilities: z.array(z.string()),
  expiresAt: z.number().int().positive(),
  displayName: z.string().optional(),
})
export type PortalSession = z.infer<typeof sessionSchema>
export type Role = PortalSession['role']
export interface LoginInput {
  email: string
  password: string
  role: Role
}
export interface PatientRegistrationInput {
  displayName: string
  email: string
  password: string
  clinicId: string
  clinicianId: string
}
export interface IdentityProvider {
  demoLogin?: boolean
  accountAuth?: boolean
  getSession: () => Promise<unknown>
  signIn?: (input?: LoginInput) => Promise<void>
  registerPatient?: (input: PatientRegistrationInput) => Promise<void>
  signOut?: () => Promise<void>
  refreshSession?: () => Promise<unknown>
  subscribe?: (callback: () => void) => () => void
}
declare global {
  interface Window {
    /** In-memory auth adapter injected before React mounts. Tokens are not persisted by this portal. */
    wellqIdentity?: IdentityProvider
    wellqDemoSelection?: {
      role?: Role
      clientId?: string
      clinicianId?: string
      patientId?: string
    }
  }
}
