import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  Activity,
  LayoutDashboard,
  Files,
  BookOpen,
  Sun,
  Moon,
  Menu,
  X,
  ShieldCheck,
  ChevronRight,
  FlaskConical,
  TrendingUp,
  FileText,
} from 'lucide-react'
import { useRuntime } from '../app/runtime'
import { usePreferences } from '../hooks/usePreferences'
import { PatientScope } from '../features/exams/PatientScope'
import { ContinuityBanner, ConnectionIndicator } from '../components/Continuity'
import { SessionControls, SessionGate } from '../features/session/SessionControls'
import { UploadActivity } from '../features/uploads/UploadActivity'

export function PortalLayout() {
  const { t, i18n } = useTranslation()
  const runtime = useRuntime()
  const { theme, toggleTheme } = usePreferences()
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const main = useRef<HTMLElement>(null)
  const previousPath = useRef(location.pathname)
  const menuButton = useRef<HTMLButtonElement>(null)
  const navigation = useRef<HTMLElement>(null)
  function closeMenu() {
    setOpen(false)
    menuButton.current?.focus()
  }
  useEffect(() => {
    if (previousPath.current !== location.pathname) main.current?.focus({ preventScroll: true })
    previousPath.current = location.pathname
  }, [location.pathname])
  const home = runtime.role === 'clinician' ? '/clinical' : '/patient'
  const title =
    location.pathname === '/history'
      ? 'recordsHistoryNav'
      : location.pathname === '/reports'
        ? 'recordsReportsNav'
        : location.pathname.startsWith('/exams')
          ? 'exams'
          : location.pathname === '/upload'
            ? 'uploadTitle'
            : location.pathname === '/catalog'
              ? 'catalog'
              : 'overview'
  return (
    <>
      <a className="skip-link" href="#main-content">
        {t('skip')}
      </a>
      <div className="portal-shell">
        <aside
          ref={navigation}
          className={`sidebar ${open ? 'is-open' : ''}`}
          id="portal-navigation"
          onKeyDown={(event) => {
            if (event.key === 'Escape') closeMenu()
          }}
        >
          <button
            className="icon-button mobile-close"
            onClick={closeMenu}
            aria-label={t('closeMenu')}
          >
            <X size={22} aria-hidden="true" />
          </button>
          <NavLink className="brand" to={home} onClick={() => setOpen(false)}>
            <span className="brand-mark">
              <Activity size={25} aria-hidden="true" />
            </span>
            <span>
              {t('brand')}
              <small>{t('portal')}</small>
            </span>
          </NavLink>
          <span className="nav-group-label">{t('workspace')}</span>
          <nav aria-label={t('workspace')}>
            <NavLink to={home} onClick={() => setOpen(false)}>
              <LayoutDashboard size={19} aria-hidden="true" />
              {t('overview')}
            </NavLink>
            <NavLink to="/exams" onClick={() => setOpen(false)}>
              <Files size={19} aria-hidden="true" />
              {t('exams')}
            </NavLink>
            {runtime.role === 'clinician' && (
              <>
                <NavLink to="/history" onClick={() => setOpen(false)}>
                  <TrendingUp size={19} aria-hidden="true" />
                  {t('recordsHistoryNav')}
                </NavLink>
                <NavLink to="/reports" onClick={() => setOpen(false)}>
                  <FileText size={19} aria-hidden="true" />
                  {t('recordsReportsNav')}
                </NavLink>
              </>
            )}
            {runtime.role === 'patient' && (
              <NavLink to="/upload" onClick={() => setOpen(false)}>
                <Files size={19} aria-hidden="true" />
                {t('uploadTitle')}
              </NavLink>
            )}
          </nav>
          <span className="nav-group-label">{t('resources')}</span>
          <nav aria-label={t('resources')}>
            <NavLink to="/catalog" onClick={() => setOpen(false)}>
              <BookOpen size={19} aria-hidden="true" />
              {t('catalog')}
            </NavLink>
          </nav>
          <div className="sidebar-bottom">
            <ShieldCheck size={19} aria-hidden="true" />
            <strong>{t('privacy')}</strong>
            <p>{t('serverAuthority')}</p>
          </div>
        </aside>
        <div className="main-shell">
          <header className="topbar">
            <div className="breadcrumb">
              <button
                className="icon-button mobile-menu"
                aria-label={t(open ? 'closeMenu' : 'menu')}
                aria-expanded={open}
                aria-controls="portal-navigation"
                ref={menuButton}
                onClick={() => {
                  if (open) closeMenu()
                  else {
                    setOpen(true)
                    window.requestAnimationFrame(() =>
                      navigation.current?.querySelector<HTMLAnchorElement>('a')?.focus(),
                    )
                  }
                }}
              >
                {open ? <X size={21} /> : <Menu size={21} />}
              </button>
              <span>{t(runtime.role === 'clinician' ? 'clinical' : 'patient')}</span>
              <ChevronRight size={13} aria-hidden="true" />
              <strong>{t(title)}</strong>
            </div>
            <div className="toolbar">
              <label className="sr-only" htmlFor="language">
                {t('language')}
              </label>
              <select
                id="language"
                value={i18n.language}
                onChange={(e) => void i18n.changeLanguage(e.target.value)}
              >
                <option value="es">ES</option>
                <option value="en">EN</option>
              </select>
              <button
                className="icon-button"
                aria-label={t(theme === 'light' ? 'dark' : 'light')}
                onClick={toggleTheme}
              >
                {theme === 'light' ? <Moon size={19} /> : <Sun size={19} />}
              </button>
              <span className="toolbar-divider" />
              {runtime.mode === 'demo' ? (
                <>
                  <label className="sr-only" htmlFor="demo-role">
                    {t('demoRole')}
                  </label>
                  <select
                    id="demo-role"
                    value={runtime.role}
                    onChange={(e) => runtime.setDemoRole(e.target.value as 'clinician' | 'patient')}
                  >
                    <option value="clinician">{t('clinician')}</option>
                    <option value="patient">{t('patientRole')}</option>
                  </select>
                </>
              ) : (
                <span className="review-label">
                  {t(
                    runtime.session
                      ? runtime.role === 'clinician'
                        ? 'clinician'
                        : 'patientRole'
                      : 'session',
                  )}
                </span>
              )}
            </div>
          </header>
          <div className="session-strip">
            <ConnectionIndicator />
            <SessionControls />
          </div>
          {runtime.mode === 'demo' && (
            <div className="demo-banner">
              <FlaskConical size={15} aria-hidden="true" />
              <span>{t('demoNotice')}</span>
            </div>
          )}
          <main className="content" id="main-content" ref={main} tabIndex={-1}>
            <ContinuityBanner />
            {runtime.mode === 'api' && !runtime.session ? (
              <SessionGate />
            ) : (
              <PatientScope key={`${runtime.role}:${runtime.boundary}`}>
                <UploadActivity />
                <Outlet />
              </PatientScope>
            )}
          </main>
          <footer className="footer">
            <span>
              {t('brand')} · {t('tagline')}
            </span>
            <span className="mode-indicator">{t(runtime.mode === 'demo' ? 'demo' : 'api')}</span>
          </footer>
        </div>
      </div>
    </>
  )
}
