import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import { getPatientsToReview, markNotADuplicate } from '../services/api'

const person = (p) => `${p.first_name} ${p.last_name} (${p.patient_id}), born ${p.birth_date}`

function ReviewRow({ item, onCleared }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const clear = async () => {
    setBusy(true)
    setError(null)
    try {
      await markNotADuplicate(item.patient_id)
      onCleared()
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }
  return (
    <li className="py-3 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium text-gray-900">{person(item)}</p>
          <p className="text-gray-600">May be: {item.possible_matches.map(person).join('; ')}</p>
        </div>
        <button type="button" className="btn-secondary btn-sm" disabled={busy} onClick={clear}>
          Different person
        </button>
      </div>
      {error && (
        <p role="alert" className="mt-1 text-red-700">
          Could not update this patient — {error}
        </p>
      )}
    </li>
  )
}

/**
 * Patients added from a claim who may be someone already on the list. Their claims are still
 * checked; nothing is merged. Shows nothing when there's no one to check, or for a role that
 * can't see patient details.
 */
export default function PatientReviewCard() {
  const { data, reload } = useApi((options) => getPatientsToReview(options))
  if (!data?.length) return null
  return (
    <section aria-label="Patients to check" className="card space-y-1 p-6">
      <h2 className="text-[15px] font-semibold text-gray-900">
        {data.length === 1 ? '1 patient to check' : `${data.length} patients to check`}
      </h2>
      <p className="text-sm text-gray-500">
        These patients were added from a claim and may already be on your list. Their claims are still checked, and the
        records are kept separate. Compare them with your hospital’s register.
      </p>
      <ul className="divide-y divide-gray-100">
        {data.map((item) => (
          <ReviewRow key={item.patient_id} item={item} onCleared={reload} />
        ))}
      </ul>
    </section>
  )
}
