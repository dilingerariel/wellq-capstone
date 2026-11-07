import { useTranslation } from 'react-i18next'
import { ShieldCheck } from 'lucide-react'
export function UploadPreparation() {
  const { t } = useTranslation()
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
      <p>{t('uploadPreparationPending')}</p>
    </section>
  )
}
