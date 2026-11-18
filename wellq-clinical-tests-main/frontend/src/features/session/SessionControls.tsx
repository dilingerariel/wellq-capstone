import { useState, useEffect, type FormEvent } from 'react'
import { Activity, Building2, LockKeyhole, LogIn, LogOut, RefreshCw, UserCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'
import { useRuntime } from '../../app/runtime'

interface ClinicOption {
  id: string
  name: string
  clinicians: Array<{ id: string; name: string }>
}

export function SessionControls() {
  const { t } = useTranslation()
  const runtime = useRuntime()
  if (runtime.mode !== 'api') return null
  return (
    <div className="session-controls">
      <span className="review-label" role="status">
        {t(`session_${runtime.sessionPhase}`)}
      </span>
      {runtime.session && (
        <>
          <span
            className="session-badge"
            style={{
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '12px',
              fontWeight: 600,
              background: '#e0f2fe',
              color: '#0369a1',
              border: '1px solid #bae6fd',
            }}
          >
            {runtime.session.tenantId} · {runtime.session.resourceId}
          </span>
          {(runtime.canRenew || runtime.sessionPhase === 'unverified') && (
            <button
              className="icon-button"
              disabled={runtime.loading || runtime.connection !== 'online'}
              aria-label={t('renewSession')}
              onClick={runtime.reloadIdentity}
            >
              <RefreshCw size={18} aria-hidden="true" />
            </button>
          )}
          <button className="button secondary" onClick={runtime.signOut}>
            <LogOut size={16} aria-hidden="true" />
            {t('signOut')}
          </button>
        </>
      )}
    </div>
  )
}

export function SessionGate() {
  const { t } = useTranslation()
  const runtime = useRuntime()
  const { pathname } = useLocation()
  // Presentation only. The identity provider and backend still decide the role.
  const patientEntry =
    /^\/(patient|upload)(\/|$)/.test(pathname) || pathname.endsWith('/extraction')
  const disabled = runtime.loading || runtime.connection !== 'online'

  const demoLogin = window.wellqIdentity?.demoLogin === true
  const accountAuth = window.wellqIdentity?.accountAuth === true
  const [clinics, setClinics] = useState<ClinicOption[]>([])
  const [clinicsFailed, setClinicsFailed] = useState(false)
  const [selectedClinic, setSelectedClinic] = useState('')
  const [selectedDoctor, setSelectedDoctor] = useState('')
  const [registering, setRegistering] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!demoLogin && !(accountAuth && patientEntry && registering)) return
    let active = true
    const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    fetch(`${apiBase}/${accountAuth ? 'auth/clinics' : 'demo/clinics'}`, { credentials: 'omit', redirect: 'error' })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (active && Array.isArray(data) && data.length > 0) {
          setClinics(data)
          setSelectedClinic(data[0].id)
          setSelectedDoctor(data[0].clinicians?.[0]?.id || '')
        } else if (active) {
          setClinicsFailed(true)
        }
      })
      .catch(() => {
        if (active) setClinicsFailed(true)
      })
    return () => {
      active = false
    }
  }, [demoLogin, accountAuth, patientEntry, registering])

  const currentClinic = clinics.find((c) => c.id === selectedClinic) || clinics[0]

  const handleSignIn = () => {
    if (demoLogin) {
      window.wellqDemoSelection = {
        role: patientEntry ? 'patient' : 'clinician',
        clientId: selectedClinic,
        clinicianId: selectedDoctor,
        patientId: 'paciente_ariel_demo',
      }
    }
    runtime.signIn()
  }

  const handleAccountSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFormError('')
    setSubmitting(true)
    try {
      if (patientEntry && registering) {
        if (!selectedClinic || !selectedDoctor) throw new Error('Selecciona una clínica y un clínico habilitados.')
        const completed = await runtime.registerPatient({
          displayName, email, password, clinicId: selectedClinic, clinicianId: selectedDoctor,
        })
        if (!completed) throw new Error('No se pudo crear la cuenta. Revisa los datos o inicia sesión si ya existe.')
      } else {
        const completed = await runtime.signIn({ email, password, role: patientEntry ? 'patient' : 'clinician' })
        if (!completed) throw new Error('Correo o contraseña incorrectos, o cuenta deshabilitada.')
      }
    } catch (error) {
      setFormError(error instanceof Error ? error.message : 'No se pudo completar el acceso.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="access-card" aria-labelledby="access-title" aria-busy={runtime.loading}>
      <div className="access-brand">
        <span className="access-mark">
          <Activity size={27} aria-hidden="true" />
        </span>
        <span>
          {t('brand')}
          <small>{t(patientEntry ? 'portal' : 'accessClinical')}</small>
        </span>
      </div>
      <div className="access-intro">
        <h1 id="access-title">{t(patientEntry ? 'accessPatient' : 'accessProfessional')}</h1>
        <p>{t(patientEntry ? 'accessPatientIntro' : 'accessProfessionalIntro')}</p>
      </div>

      {!patientEntry && demoLogin && (
        <div
          className="demo-clinic-selector"
          style={{
            margin: '18px 0',
            padding: '16px',
            borderRadius: '12px',
            border: '1px solid var(--border)',
            background: 'var(--surface-subtle, #f8fafc)',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label
              htmlFor="clinic-select"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '13px',
                fontWeight: 600,
              }}
            >
              <Building2 size={16} aria-hidden="true" />
              Clínica (Tenant):
            </label>
            <select
              id="clinic-select"
              value={selectedClinic}
              onChange={(e) => {
                const clinic = clinics.find((item) => item.id === e.target.value)
                setSelectedClinic(e.target.value)
                setSelectedDoctor(clinic?.clinicians[0]?.id || '')
              }}
              disabled={disabled}
              style={{
                padding: '8px 12px',
                borderRadius: '8px',
                border: '1px solid var(--border)',
                background: 'var(--surface)',
                color: 'inherit',
                fontSize: '14px',
              }}
            >
              {clinics.map((clinic) => (
                <option key={clinic.id} value={clinic.id}>
                  {clinic.name} ({clinic.id})
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label
              htmlFor="doctor-select"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '13px',
                fontWeight: 600,
              }}
            >
              <UserCheck size={16} aria-hidden="true" />
              Médico / Profesional:
            </label>
            <select
              id="doctor-select"
              value={selectedDoctor}
              onChange={(e) => setSelectedDoctor(e.target.value)}
              disabled={disabled}
              style={{
                padding: '8px 12px',
                borderRadius: '8px',
                border: '1px solid var(--border)',
                background: 'var(--surface)',
                color: 'inherit',
                fontSize: '14px',
              }}
            >
              {currentClinic?.clinicians.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {accountAuth && patientEntry && registering && (
        <div className="demo-clinic-selector">
          <label htmlFor="patient-clinic-select">Clínica donde recibe atención</label>
          <select id="patient-clinic-select" value={selectedClinic} onChange={(e) => {
            const clinic = clinics.find((item) => item.id === e.target.value)
            setSelectedClinic(e.target.value)
            setSelectedDoctor(clinic?.clinicians[0]?.id || '')
          }} disabled={disabled || submitting} required>
            <option value="">Seleccionar clínica</option>
            {clinics.map((clinic) => <option key={clinic.id} value={clinic.id}>{clinic.name}</option>)}
          </select>
          <label htmlFor="patient-clinician-select">Profesional que lo atiende</label>
          <select id="patient-clinician-select" value={selectedDoctor} onChange={(e) => setSelectedDoctor(e.target.value)}
            disabled={disabled || submitting || !currentClinic} required>
            <option value="">Seleccionar profesional</option>
            {currentClinic?.clinicians.map((doctor) => <option key={doctor.id} value={doctor.id}>{doctor.name}</option>)}
          </select>
          {clinicsFailed && <p role="alert">No se pudieron cargar las clínicas. Intenta de nuevo más tarde.</p>}
          {clinics.length === 0 && !clinicsFailed && <p role="status">Aún no hay clínicos activos registrados para seleccionar.</p>}
        </div>
      )}

      <div
        className={`access-status${runtime.sessionPhase === 'error' ? ' access-status-error' : ''}`}
        role={runtime.sessionPhase === 'error' ? 'alert' : 'status'}
      >
        {runtime.loading && <RefreshCw className="access-spinner" size={18} aria-hidden="true" />}
        <span>{t(`session_${runtime.sessionPhase}`)}</span>
      </div>
      {demoLogin && !patientEntry && clinicsFailed && (
        <p role="alert">{t('demoClinicsUnavailable')}</p>
      )}
      <p className="access-help">
        {accountAuth
          ? 'Acceso de demostración con datos sintéticos. No usar para atención clínica real.'
          : t(runtime.canSignIn ? 'accessDelegatedHelp' : 'accessProviderHelp')}
      </p>
      {accountAuth ? (
        <form className="session-actions access-actions" onSubmit={handleAccountSubmit}>
          {patientEntry && registering && (
            <label>Nombre completo
              <input autoComplete="name" minLength={2} maxLength={120} value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
            </label>
          )}
          <label>Correo electrónico
            <input type="email" autoComplete="email" maxLength={255} value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>Contraseña
            <input type="password" autoComplete={patientEntry && registering ? 'new-password' : 'current-password'} minLength={patientEntry && registering ? 12 : 1} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          {patientEntry && registering && <small>Usa una contraseña de al menos 12 caracteres. Guarda tu contraseña; no podemos recuperarla.</small>}
          {formError && <p role="alert">{formError}</p>}
          <button className="button primary" type="submit" disabled={disabled || submitting || (patientEntry && registering && clinics.length === 0)}>
            <LogIn size={17} aria-hidden="true" />{submitting ? 'Procesando…' : patientEntry && registering ? 'Crear cuenta de paciente' : t('signIn')}
          </button>
          {patientEntry && <button className="button secondary" type="button" disabled={submitting} onClick={() => { setRegistering(!registering); setFormError('') }}>
            {registering ? 'Ya tengo cuenta · Iniciar sesión' : '¿Nuevo paciente? · Registrarme'}
          </button>}
          {!patientEntry && <Link to="/admin">Administración de clínicos</Link>}
        </form>
      ) : <div className="session-actions access-actions">
        {runtime.canSignIn && (
          <button
            className="button primary"
            disabled={disabled || (demoLogin && !patientEntry && clinics.length === 0)}
            onClick={handleSignIn}
          >
            <LogIn size={17} aria-hidden="true" />
            {t(runtime.loading ? 'loadingSession' : 'signIn')}
          </button>
        )}
        <button className="button secondary" disabled={disabled} onClick={runtime.reloadIdentity}>
          <RefreshCw size={17} aria-hidden="true" />
          {t('reloadIdentity')}
        </button>
      </div>}
      {accountAuth && !patientEntry && <p className="access-help"><Link to="/patient">Acceso de pacientes</Link></p>}
      {runtime.connection !== 'online' && <p className="access-offline">{t('accessOffline')}</p>}
      <p className="access-footnote">
        <LockKeyhole size={16} aria-hidden="true" />
        {t('accessScope')}
      </p>
    </section>
  )
}
