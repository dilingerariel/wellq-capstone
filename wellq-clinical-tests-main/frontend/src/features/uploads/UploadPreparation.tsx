import { useTranslation } from 'react-i18next'
import { ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useRuntime } from '../../app/runtime'
export function UploadPreparation() {
  const { t } = useTranslation()
  const { mode } = useRuntime()
  return (
    <section className="panel upload-preparation">
      <h2>
        <ShieldCheck size={20} aria-hidden="true" />
        {t('uploadPreparation')}
      </h2>
      <ol>
        {['uploadStepHash', 'uploadStepInitiate', 'uploadStepTransfer', 'uploadStepVerify'].map(
          (key) => (
            <li key={key}>{t(key)}</li>
          ),
        )}
      </ol>
      <p>{t(mode === 'demo' ? 'uploadDemoBlocked' : 'uploadMemoryHelp')}</p>
      <Link className="button primary" to="/upload">
        {t('uploadTitle')}
      </Link>
    </section>
  )
}
