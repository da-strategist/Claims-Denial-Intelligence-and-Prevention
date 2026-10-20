import { useState } from 'react'
import Icon from './Icon'
import { ValidationBadge } from './StatusBadge'

const DAY_MS = 24 * 60 * 60 * 1000

const shortDate = (iso) =>
  new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })

function Group({ title, hint, count, children }) {
  return (
    <section className="space-y-1">
      <div className="flex items-baseline justify-between gap-2 px-1">
        <h3 className="eyebrow">{title}</h3>
        <span className="text-xs tabular-nums text-gray-400">{count}</span>
      </div>
      <p className="px-1 text-xs text-gray-400">{hint}</p>
      {count === 0 ? (
        <p className="px-1 py-3 text-sm text-gray-400">None</p>
      ) : (
        <ul className="-mx-1 space-y-0.5 pt-1">{children}</ul>
      )}
    </section>
  )
}

/** Whole-row button; `active` marks the one open in the main column. */
function RowButton({ active, onClick, label, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-current={active ? 'true' : undefined}
      className={`block w-full min-w-0 rounded-xl px-3 py-2.5 text-left transition-colors ${
        active ? 'bg-accent-soft ring-1 ring-accent/20' : 'hover:bg-gray-50'
      }`}
    >
      {children}
    </button>
  )
}

function SavedDraftRow({ row, now, active, onOpen, onDelete }) {
  const [confirming, setConfirming] = useState(false)
  const name = row.patient_name ?? row.patient_id ?? 'No patient yet'
  const daysLeft = Math.ceil((new Date(row.expires_at) - now) / DAY_MS)
  if (confirming) {
    return (
      <li className="flex items-center justify-between gap-2 rounded-xl bg-red-50 px-3 py-2.5 text-sm">
        <span className="min-w-0 truncate text-red-800">Delete {name}?</span>
        <span className="flex shrink-0 gap-1">
          <button type="button" className="btn-danger btn-sm" onClick={() => onDelete(row)}>
            Delete
          </button>
          <button type="button" className="btn-secondary btn-sm" onClick={() => setConfirming(false)}>
            Keep
          </button>
        </span>
      </li>
    )
  }
  return (
    <li className="relative">
      <RowButton active={active} onClick={() => onOpen(row)} label={`Open saved draft: ${name}`}>
        <div className="truncate pr-7 text-sm font-medium text-gray-900">{name}</div>
        <div className="truncate text-xs text-gray-500">
          {row.lines} {row.lines === 1 ? 'procedure' : 'procedures'} · {row.updated_by} ·{' '}
          {shortDate(row.updated_at)}
        </div>
        {daysLeft <= 3 && (
          <div className="text-xs text-amber-700">
            {daysLeft <= 1 ? 'Expires today' : `Expires in ${daysLeft} days`}
          </div>
        )}
      </RowButton>
      <button
        type="button"
        onClick={() => setConfirming(true)}
        aria-label={`Delete saved draft: ${name}`}
        className="absolute top-2.5 right-2 rounded-lg p-1 text-gray-400 hover:bg-red-50 hover:text-red-600 focus:text-red-600"
      >
        <Icon name="trash" className="h-4 w-4" />
      </button>
    </li>
  )
}

function DraftClaimRow({ claim, validation, payerName, active, onOpen }) {
  return (
    <li>
      <RowButton active={active} onClick={() => onOpen(claim)} label={`Open draft claim ${claim.claim_id}`}>
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium text-gray-900">{claim.claim_id}</span>
          {validation && <ValidationBadge status={validation.status} />}
        </div>
        <div className="truncate text-xs text-gray-500">
          {claim.patient_id} · {payerName ?? claim.payer_id} · {shortDate(claim.service_date)}
        </div>
      </RowButton>
    </li>
  )
}

/**
 * Everything waiting to be finished, shared by everyone who enters claims: saved forms
 * (not validated yet) and created claims that haven't been submitted.
 */
export default function DraftsPanel({
  savedDrafts,
  draftClaims,
  validations,
  payers,
  open,
  onOpenSaved,
  onDeleteSaved,
  onOpenClaim,
}) {
  // Expiry is shown in whole days, so the time the panel was first shown is close enough
  const [now] = useState(() => Date.now())
  const saved = savedDrafts ?? []
  const claims = draftClaims ?? []
  return (
    <aside aria-labelledby="drafts-title" className="card space-y-5 p-4">
      <div className="px-1">
        <h2 id="drafts-title" className="text-[15px] font-semibold text-gray-900">
          Drafts
        </h2>
        <p className="text-xs text-gray-500">Shared with everyone who enters claims</p>
      </div>
      <Group title="Saved forms" hint="Not validated yet · kept 30 days" count={saved.length}>
        {saved.map((row) => (
          <SavedDraftRow
            key={row.id}
            row={row}
            now={now}
            active={open?.kind === 'saved' && open.id === row.id}
            onOpen={onOpenSaved}
            onDelete={onDeleteSaved}
          />
        ))}
      </Group>
      <div className="border-t border-gray-100" />
      <Group title="Draft claims" hint="Validated · waiting to be submitted" count={claims.length}>
        {claims.map((claim) => (
          <DraftClaimRow
            key={claim.claim_id}
            claim={claim}
            validation={validations?.[claim.claim_id]}
            payerName={payers?.[claim.payer_id]?.payer_name}
            active={open?.kind === 'claim' && open.id === claim.claim_id}
            onOpen={onOpenClaim}
          />
        ))}
      </Group>
    </aside>
  )
}
