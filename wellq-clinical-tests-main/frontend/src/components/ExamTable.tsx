import { ArrowUpRight, FileText } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { StatusBadge } from './StatusBadge'
import type { Exam } from '../types/clinical'
import { formatDate } from '../lib/format'
export function ExamTable({ items }: { items: Exam[] }) {
  const { t, i18n } = useTranslation()
  return (
    <div className="table-scroll" role="region" aria-label={t('examTitle')} tabIndex={0}>
      <table>
        <caption className="sr-only">{t('examTitle')}</caption>
        <thead>
          <tr>
            {['document', 'date', 'status', 'review', 'actions'].map((k) => (
              <th key={k} scope="col">
                {t(k)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((exam) => (
            <tr key={exam.clinical_test_id}>
              <td>
                <div className="document-cell">
                  <span className="file-icon">
                    <FileText size={19} aria-hidden="true" />
                  </span>
                  <div>
                    <Link
                      className="document-title"
                      to={`/exams/${encodeURIComponent(exam.clinical_test_id)}`}
                    >
                      {exam.title}
                    </Link>
                    <span className="subtext">{t(`type_${exam.test_type}`)}</span>
                  </div>
                </div>
              </td>
              <td className="date-cell">{formatDate(exam.test_date, i18n.language)}</td>
              <td>
                <StatusBadge status={exam.status} />
              </td>
              <td>
                <span
                  className={`review-label ${exam.review.status === 'reviewed' ? 'reviewed' : ''}`}
                >
                  {t(`review_${exam.review.status}`)}
                </span>
              </td>
              <td>
                <Link
                  className="icon-button"
                  aria-label={`${t('viewExam')}: ${exam.title}`}
                  to={`/exams/${encodeURIComponent(exam.clinical_test_id)}`}
                >
                  <ArrowUpRight size={19} aria-hidden="true" />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
