import { useState } from 'react'
import { useClaims, usePayerLookup } from '../hooks/useClaims'

const PAGE_SIZE = 25

const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

const STATUS_STYLES = {
  Paid: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  Denied: 'bg-red-50 text-red-800 border-red-200',
}

function ClaimStatusBadge({ status }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${STATUS_STYLES[status] ?? 'bg-gray-50 text-gray-700 border-gray-200'}`}
    >
      {status}
    </span>
  )
}

const COLUMNS = [
  { label: 'Claim ID' },
  { label: 'Service Date' },
  { label: 'Patient' },
  { label: 'Payer' },
  { label: 'Type' },
  { label: 'Status' },
  { label: 'Charge', align: 'right' },
  { label: 'Paid', align: 'right' },
  { label: 'Days in AR', align: 'right' },
]

function ClaimRow({ claim, payerName }) {
  return (
    <tr className="border-b border-gray-50 hover:bg-gray-50">
      <td className="px-4 py-3 text-sm font-medium text-gray-900">{claim.claim_id}</td>
      <td className="px-4 py-3 text-sm text-gray-600">{claim.service_date}</td>
      <td className="px-4 py-3 text-sm text-gray-600">{claim.patient_id}</td>
      <td className="px-4 py-3 text-sm text-gray-700">{payerName ?? claim.payer_id}</td>
      <td className="px-4 py-3 text-sm text-gray-600">{claim.claim_type}</td>
      <td className="px-4 py-3">
        <ClaimStatusBadge status={claim.status} />
      </td>
      <td className="px-4 py-3 text-right text-sm font-medium text-gray-900">
        {currency.format(claim.total_charge)}
      </td>
      <td className="px-4 py-3 text-right text-sm text-gray-600">
        {currency.format(claim.total_paid)}
      </td>
      <td className="px-4 py-3 text-right text-sm text-gray-600">{claim.days_in_ar}</td>
    </tr>
  )
}

function Pagination({ page, pages, total, pageSize, onPageChange, disabled }) {
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1
  const last = Math.min(page * pageSize, total)
  const buttonClass =
    'px-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed'

  return (
    <div className="flex items-center justify-between">
      <div className="text-sm text-gray-500">
        Showing {first.toLocaleString()}–{last.toLocaleString()} of {total.toLocaleString()}
      </div>
      <div className="flex items-center gap-2">
        <button
          className={buttonClass}
          onClick={() => onPageChange(page - 1)}
          disabled={disabled || page <= 1}
        >
          Previous
        </button>
        <span className="text-sm text-gray-600">
          Page {page.toLocaleString()} of {pages.toLocaleString()}
        </span>
        <button
          className={buttonClass}
          onClick={() => onPageChange(page + 1)}
          disabled={disabled || page >= pages}
        >
          Next
        </button>
      </div>
    </div>
  )
}

export default function ClaimsWorkbench() {
  const [page, setPage] = useState(1)
  const { data, loading, error } = useClaims({ page, page_size: PAGE_SIZE })
  const payers = usePayerLookup()

  return (
    <div className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Claims Workbench</h1>
        {data && (
          <div className="text-sm text-gray-500">{data.total.toLocaleString()} claims</div>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          Could not load claims — {error}
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-gray-100 bg-white shadow-sm">
        <table className={`w-full transition-opacity ${loading && data ? 'opacity-50' : ''}`}>
          <thead>
            <tr className="border-b border-gray-100">
              {COLUMNS.map(({ label, align }) => (
                <th
                  key={label}
                  className={`px-4 py-3 text-xs font-semibold uppercase text-gray-500 ${align === 'right' ? 'text-right' : 'text-left'}`}
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data?.items.map((claim) => (
              <ClaimRow
                key={claim.claim_id}
                claim={claim}
                payerName={payers[claim.payer_id]?.payer_name}
              />
            ))}
            {!data && loading && (
              <tr>
                <td colSpan={COLUMNS.length} className="px-4 py-10 text-center text-sm text-gray-500">
                  Loading claims…
                </td>
              </tr>
            )}
            {data?.items.length === 0 && (
              <tr>
                <td colSpan={COLUMNS.length} className="px-4 py-10 text-center text-sm text-gray-500">
                  No claims found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {data && (
        <Pagination
          page={data.page}
          pages={data.pages}
          total={data.total}
          pageSize={data.page_size}
          onPageChange={setPage}
          disabled={loading}
        />
      )}
    </div>
  )
}
