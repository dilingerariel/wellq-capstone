import { createContext, useContext, useState, type ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useTranslation } from 'react-i18next'
import { UserRound, ArrowRight } from 'lucide-react'
import { useRuntime } from '../../app/runtime'

const schema = z.object({ patient: z.string().trim().min(1).max(200).regex(/^\S+$/) })
const Context = createContext({ patientId: '' })
export function PatientScope({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const { role, mode, session } = useRuntime()
  const [selected, setSelected] = useState('')
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) })
  const patientId =
    mode === 'demo' ? 'demo-patient' : role === 'patient' ? session?.resourceId || '' : selected
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
            <form onSubmit={handleSubmit((v) => setSelected(v.patient))}>
              <div>
                <label htmlFor="patient-id">{t('authorizedPatient')}</label>
                <input
                  id="patient-id"
                  autoComplete="off"
                  {...register('patient')}
                  aria-invalid={Boolean(errors.patient)}
                  aria-describedby="patient-help"
                />
              </div>
              <button className="button secondary" type="submit">
                {t('selectPatient')}
                <ArrowRight size={15} aria-hidden="true" />
              </button>
              <p id="patient-help" className={errors.patient ? 'field-error' : 'subtext'}>
                {t(errors.patient ? 'patientRequired' : 'patientIdHelp')}
              </p>
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
