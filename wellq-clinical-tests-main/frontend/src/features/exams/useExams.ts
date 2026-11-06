import { useQuery } from '@tanstack/react-query'
import { useRuntime } from '../../app/runtime'
import { usePatientScope } from './PatientScope'
import type { ExamFilters } from '../../types/clinical'
export function useExams(filters: ExamFilters = {}) {
  const { source, session, role } = useRuntime()
  const { patientId } = usePatientScope()
  const allowed = !session || session.permissions.includes('clinical:read')
  const query = useQuery({
    queryKey: ['exams', role, patientId, filters],
    queryFn: ({ signal }) => source!.list(filters, patientId, signal),
    enabled: Boolean(source && patientId && allowed),
  })
  return { ...query, needsPatient: !patientId, allowed }
}
