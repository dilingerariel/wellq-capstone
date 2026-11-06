import { Navigate, Route, Routes, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { lazy, Suspense, type ReactNode } from 'react'
import type { Role } from '../types/session'
import { useRuntime } from './runtime'
import { PortalLayout } from '../layouts/PortalLayout'
import { Loading } from '../components/States'
const OverviewPage = lazy(() =>
  import('../features/overview/OverviewPage').then((m) => ({ default: m.OverviewPage })),
)
const ExamsPage = lazy(() =>
  import('../features/exams/ExamsPage').then((m) => ({ default: m.ExamsPage })),
)
const ExamDetailPage = lazy(() =>
  import('../features/exams/ExamDetailPage').then((m) => ({ default: m.ExamDetailPage })),
)
const CatalogPage = lazy(() =>
  import('../features/catalog/CatalogPage').then((m) => ({ default: m.CatalogPage })),
)
function Home() {
  const { role } = useRuntime()
  return <Navigate replace to={role === 'clinician' ? '/clinical' : '/patient'} />
}
function RoleGuard({ role, children }: { role: Role; children: ReactNode }) {
  const runtime = useRuntime()
  const { t } = useTranslation()
  return runtime.role === role ? (
    children
  ) : (
    <section className="panel state" role="alert">
      <h1>{t('forbidden')}</h1>
      <Link to="/" className="button secondary">
        {t('goHome')}
      </Link>
    </section>
  )
}
function NotFound() {
  const { t } = useTranslation()
  return (
    <div className="panel state">
      <h1>{t('notFound')}</h1>
      <Link to="/" className="button primary">
        {t('goHome')}
      </Link>
    </div>
  )
}
export function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route element={<PortalLayout />}>
          <Route index element={<Home />} />
          <Route
            path="clinical"
            element={
              <RoleGuard role="clinician">
                <OverviewPage />
              </RoleGuard>
            }
          />
          <Route
            path="patient"
            element={
              <RoleGuard role="patient">
                <OverviewPage />
              </RoleGuard>
            }
          />
          <Route path="exams" element={<ExamsPage />} />
          <Route path="exams/:id" element={<ExamDetailPage />} />
          <Route path="catalog" element={<CatalogPage />} />
          <Route path="dashboard/*" element={<Home />} />
          <Route path="demo" element={<Home />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
