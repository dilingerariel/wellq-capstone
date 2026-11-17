import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useTranslation } from 'react-i18next'
import { UserRound, ArrowRight } from 'lucide-react'
import { useRuntime } from '../../app/runtime'
import { useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'

const schema = z.object({ patient: z.string().trim().min(1).max(200).regex(/^\S+$/) })
const Context = createContext({ patientId: '' })
export function PatientScope({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const { role, mode, session, canRequest, clinician, reportExport } = useRuntime()
  const [selected, setSelected] = useState('')
  const client = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) })
  const patientId =
    mode === 'demo' ? 'demo-patient' : role === 'patient' ? session?.resourceId || '' : selected
  useEffect(() => {
    if (mode === 'api' && role === 'clinician' && session?.tenantId === 'clinica_alemana' &&
        session.resourceId === 'rene_faundez' && import.meta.env.VITE_DEMO_AUTH_ENABLED === 'true') {
      setSelected('paciente_ariel_demo')
    }
  }, [mode, role, session?.tenantId, session?.resourceId])
  return (
    <Context.Provider value={{ patientId }}>
      {role === 'clinician' && (
        <section className="patient-scope" aria-label={t('patientContext')}>
          <span className="patient-avatar">
            <UserRound size={20} aria-hidden="true" />
          </span>
          {mode === 'demo' ? (
            <div>
              <span className="eyebrow">{t('patientContext')}</span>
              <strong>{t('syntheticPatient')}</strong>
            </div>
          ) : (
            <form
              onSubmit={handleSubmit(async (v) => {
                if (canRequest) {
                  if (v.patient !== selected) {
                    if (clinician.hasWork() && !window.confirm(t('clinicalDiscard'))) return
                    clinician.clear()
                    reportExport.clear()
                    const scope = {
                      predicate: (query: { queryKey: readonly unknown[] }) =>
                        ['exams', 'exam', 'records'].includes(String(query.queryKey[0])),
                    }
                    await client.cancelQueries(scope)
                    client.removeQueries(scope)
                    if (location.pathname.startsWith('/exams/')) navigate('/exams')
                  }
                  setSelected(v.patient)
                  reset(v)
                }
              })}
            >
              <div>
                <label htmlFor="patient-id">{t('authorizedPatient')}</label>
                <input
                  id="patient-id"
                  autoComplete="off"
                  autoCapitalize="none"
                  spellCheck={false}
                  {...register('patient')}
                  aria-invalid={Boolean(errors.patient)}
                  aria-describedby="patient-help"
                />
              </div>
              <button
                className="button secondary"
                type="submit"
                disabled={!canRequest || isSubmitting}
              >
                {t('selectPatient')}
                <ArrowRight size={15} aria-hidden="true" />
              </button>
              <p id="patient-help" className={errors.patient ? 'field-error' : 'subtext'}>
                {t(errors.patient ? 'patientRequired' : 'patientIdHelp')}
              </p>
              {isDirty && (
                <p role="status" className="draft-notice">
                  {t('draftInMemory')}
                </p>
              )}
            </form>
          )}
          {mode === 'demo' && <span className="context-note">{t('serverAuthority')}</span>}
        </section>
      )}
      {children}
    </Context.Provider>
  )
}
export function usePatientScope() {
  return useContext(Context)
}
