import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Activity, LogOut, UserPlus } from 'lucide-react'

const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/v1'
interface Clinic { id: string; name: string }
interface Clinician { id: string; name: string; email: string; clinic_id: string; active: boolean }

async function readJson(response: Response) {
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const code = payload?.detail?.code
    throw new Error(code === 'INVALID_CREDENTIALS' ? 'Correo o contraseña incorrectos.' :
      code === 'RATE_LIMITED' ? 'Demasiados intentos. Espera unos minutos.' :
      code === 'ACCOUNT_EXISTS' ? 'Ese correo ya tiene una cuenta.' :
      code === 'ADMIN_NOT_CONFIGURED' ? 'La cuenta administradora aún no está configurada en el backend.' :
      `No se pudo completar la operación (HTTP ${response.status}).`)
  }
  return response.status === 204 ? null : response.json()
}

export function AdminPage() {
  const [token, setToken] = useState('')
  const [expiresAt, setExpiresAt] = useState(0)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [clinicianEmail, setClinicianEmail] = useState('')
  const [temporaryPassword, setTemporaryPassword] = useState('')
  const [clinicId, setClinicId] = useState('')
  const [clinics, setClinics] = useState<Clinic[]>([])
  const [clinicians, setClinicians] = useState<Clinician[]>([])
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!token || !expiresAt) return
    const timeout = window.setTimeout(() => {
      setToken('')
      setExpiresAt(0)
      setClinicians([])
      setMessage('La sesión administrativa expiró. Inicia sesión nuevamente.')
    }, Math.max(0, expiresAt * 1000 - Date.now()))
    return () => window.clearTimeout(timeout)
  }, [token, expiresAt])

  useEffect(() => {
    if (!token) return
    let active = true
    void fetch(`${apiBase}/auth/catalog/clinics`, { credentials: 'omit', redirect: 'error' })
      .then(readJson).then((rows: Clinic[]) => { if (active) { setClinics(rows); setClinicId(rows[0]?.id || '') } })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : 'No se pudo cargar el catálogo.') })
    void loadClinicians(token).then((rows) => { if (active) setClinicians(rows) })
      .catch((cause) => { if (active) { setError(cause instanceof Error ? cause.message : 'No se pudo consultar la lista.'); setToken('') } })
    return () => { active = false }
  }, [token])

  async function loadClinicians(accessToken: string): Promise<Clinician[]> {
    const response = await fetch(`${apiBase}/auth/admin/clinicians`, {
      headers: { Authorization: `Bearer ${accessToken}` }, credentials: 'omit', redirect: 'error',
    })
    return (await readJson(response)) as Clinician[]
  }

  async function signIn(event: FormEvent) {
    event.preventDefault(); setError(''); setBusy(true)
    try {
      const response = await fetch(`${apiBase}/auth/admin/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        credentials: 'omit', redirect: 'error', body: JSON.stringify({ email, password }),
      })
      const data = await readJson(response)
      setToken(data.accessToken); setExpiresAt(data.expiresAt); setPassword(''); setMessage('Sesión administrativa activa en este navegador.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudo iniciar sesión.') }
    finally { setBusy(false) }
  }

  async function createClinician(event: FormEvent) {
    event.preventDefault(); setError(''); setMessage(''); setBusy(true)
    try {
      const response = await fetch(`${apiBase}/auth/admin/clinicians`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        credentials: 'omit', redirect: 'error',
        body: JSON.stringify({ display_name: name, email: clinicianEmail, password: temporaryPassword, clinic_id: clinicId }),
      })
      await readJson(response)
      setMessage('Cuenta clínica creada. Entrega la contraseña temporal por un canal seguro.')
      setName(''); setClinicianEmail(''); setTemporaryPassword('')
      setClinicians(await loadClinicians(token))
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudo crear la cuenta.') }
    finally { setBusy(false) }
  }

  async function deactivate(id: string) {
    setError(''); setMessage(''); setBusy(true)
    try {
      await readJson(await fetch(`${apiBase}/auth/admin/clinicians/${encodeURIComponent(id)}`, {
        method: 'DELETE', headers: { Authorization: `Bearer ${token}` }, credentials: 'omit', redirect: 'error',
      }))
      setClinicians(await loadClinicians(token)); setMessage('Cuenta clínica desactivada.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudo desactivar la cuenta.') }
    finally { setBusy(false) }
  }

  return <main style={{ minHeight: '100vh', padding: '36px 18px', background: '#f5f8fa' }}>
    <section className="access-card" style={{ maxWidth: 760, margin: '0 auto' }}>
      <div className="access-brand"><span className="access-mark"><Activity size={27} /></span><span>WellQ<small>Administración de cuentas clínicas</small></span></div>
      <div className="access-intro"><h1>Administración de clínicos</h1><p>Solo la cuenta administradora puede crear o desactivar profesionales.</p></div>
      {!token ? <form className="session-actions access-actions" onSubmit={signIn}>
        <label>Correo administrador<input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
        <label>Contraseña<input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
        <button className="button primary" disabled={busy}>{busy ? 'Verificando…' : 'Iniciar sesión de administrador'}</button>
      </form> : <>
        <p role="status">Sesión administrativa activa · el token solo se mantiene en memoria.</p>
        <form className="session-actions access-actions" onSubmit={createClinician}>
          <h2>Crear cuenta de clínico</h2>
          <label>Nombre completo<input autoComplete="name" minLength={2} maxLength={120} value={name} onChange={(e) => setName(e.target.value)} required /></label>
          <label>Correo profesional<input type="email" autoComplete="email" maxLength={255} value={clinicianEmail} onChange={(e) => setClinicianEmail(e.target.value)} required /></label>
          <label>Clínica<select value={clinicId} onChange={(e) => setClinicId(e.target.value)} required>
            {clinics.map((clinic) => <option key={clinic.id} value={clinic.id}>{clinic.name}</option>)}
          </select></label>
          <label>Contraseña temporal (mínimo 12 caracteres)<input type="password" autoComplete="new-password" minLength={12} maxLength={128} value={temporaryPassword} onChange={(e) => setTemporaryPassword(e.target.value)} required /></label>
          <button className="button primary" disabled={busy || !clinicId}><UserPlus size={17} /> Crear clínico</button>
        </form>
        <h2>Clínicos registrados</h2>
        {clinicians.length === 0 ? <p>Aún no hay cuentas clínicas.</p> : <ul>{clinicians.map((clinician) => <li key={clinician.id}>
          {clinician.name} · {clinician.email} · {clinician.clinic_id} · {clinician.active ? 'Activo' : 'Desactivado'}
          {clinician.active && <button className="button secondary" disabled={busy} onClick={() => void deactivate(clinician.id)}>Desactivar</button>}
        </li>)}</ul>}
        <button className="button secondary" onClick={() => { setToken(''); setExpiresAt(0); setClinicians([]); setMessage('Sesión cerrada.') }}><LogOut size={16} /> Cerrar sesión admin</button>
      </>}
      {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
      <p><Link to="/clinical">Volver al acceso clínico</Link></p>
      <small>Entorno de demostración con datos sintéticos. No usar para atención clínica real.</small>
    </section>
  </main>
}
