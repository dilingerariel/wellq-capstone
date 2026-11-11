// Served only by the guarded loopback host, never imported into the application.
;(() => {
  const nonce = '__LOCAL_NONCE__'
  const professionalEntry = document.currentScript?.dataset.wellqEntry === 'clinician'
  let role = professionalEntry ? '' : 'patient'
  const listeners = new Set()
  const notify = () => listeners.forEach((fn) => fn())
  const read = async () => {
    if (!role) return null
    const response = await fetch('/__wellq_local/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-WellQ-Local': nonce },
      body: JSON.stringify({ role }),
      credentials: 'omit',
      cache: 'no-store',
      redirect: 'error',
    })
    if (!response.ok) throw new Error('Local test identity unavailable')
    return response.json()
  }
  window.wellqIdentity = {
    getSession: read,
    refreshSession: read,
    signIn: async () => {
      role = professionalEntry ? 'clinician' : role || 'patient'
    },
    signOut: async () => {
      role = ''
      notify()
    },
    subscribe: (fn) => {
      listeners.add(fn)
      return () => listeners.delete(fn)
    },
  }
  window.addEventListener(
    'DOMContentLoaded',
    () => {
      const panel = document.createElement('aside')
      panel.setAttribute('aria-label', 'Entorno sintético local')
      panel.style.cssText =
        'padding:12px;border-bottom:2px solid #b46a00;display:flex;flex-wrap:wrap;gap:12px;align-items:center;font:14px system-ui;background:#fff4d5;color:#332500'
      const notice = document.createElement('strong')
      notice.textContent = 'SOLO PRUEBAS: identidad, IA, antivirus y almacenamiento sintéticos.'
      panel.append(notice)
      for (const [value, label] of professionalEntry
        ? []
        : [
            ['patient', 'Paciente sintético'],
            ['clinician', 'Profesional sintético'],
            ['', 'Cerrar sesión'],
          ]) {
        const button = document.createElement('button')
        button.textContent = label
        button.style.cssText =
          'min-height:44px;padding:8px;white-space:normal;color:#332500;background:#fff4d5;border:1px solid #805500'
        button.addEventListener('click', () => {
          role = value
          notify()
        })
        panel.append(button)
      }
      const patient = document.createElement('span')
      patient.textContent = 'Paciente autorizado: __LOCAL_PATIENT__'
      patient.style.cssText = 'overflow-wrap:anywhere;max-width:100%'
      panel.append(patient)
      document.body.prepend(panel)
    },
    { once: true },
  )
})()
