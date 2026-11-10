import { useId, useState } from 'react'
import { INPUT_CLASS } from '../constants'
import { useApi } from '../hooks/useApi'
import { getEdiSettings, listFacilities, listPayers, saveEdiSettings } from '../services/api'

function Text({ label, hint, value, onChange }) {
  const id = useId()
  return (
    <label htmlFor={id} className="space-y-1 text-sm font-medium text-gray-800">
      <span className="block">{label}</span>
      <input id={id} className={INPUT_CLASS} value={value ?? ''} onChange={(event) => onChange(event.target.value)} />
      {hint && <span className="block text-xs font-normal text-gray-500">{hint}</span>}
    </label>
  )
}

function Group({ title, summary, children }) {
  return (
    <fieldset className="space-y-3">
      <legend className="text-sm font-semibold text-gray-900">{title}</legend>
      {summary && <p className="text-sm text-gray-500">{summary}</p>}
      <div className="grid gap-3 sm:grid-cols-2">{children}</div>
    </fieldset>
  )
}

/** Whether one kind of claim file is live yet, and if not, what's holding it back. */
function Readiness({ label, mode, missing }) {
  const live = mode === 'production' && missing.length === 0
  return (
    <div className="text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-gray-800">{label}</span>
        {live ? (
          <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800">Live</span>
        ) : (
          <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800">Test files</span>
        )}
      </div>
      {!live && (
        <p className="mt-1 text-xs text-gray-600">
          {missing.length > 0 ? `Still needed: ${missing.join(', ')}.` : 'Everything’s filled in. Choose live files below when you’re ready.'}
        </p>
      )}
    </div>
  )
}

function SettingsForm({ initial, payers, facilities, onSaved, onCancel }) {
  const [form, setForm] = useState(initial)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const set = (path, value) =>
    setForm((current) => {
      const next = structuredClone(current)
      const keys = path.split('/')
      const last = keys.pop()
      keys.reduce((node, key) => node[key], next)[last] = value
      return next
    })
  const field = (path) => {
    const value = path.split('/').reduce((node, key) => node?.[key], form)
    return { value, onChange: (next) => set(path, next) }
  }

  const save = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onSaved(await saveEdiSettings(form))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={save} aria-label="Claim file settings" className="space-y-6 border-t border-gray-100 pt-4">
      <Group title="Who the file is from" summary="The ID your billing system or clearinghouse knows you by, and who to contact about a file.">
        <Text label="Submitter ID" {...field('submitter/id')} />
        <Text label="Submitter name" {...field('submitter/name')} />
        <Text label="Submitter contact" {...field('submitter/contact_name')} />
        <Text label="Submitter phone" {...field('submitter/phone')} />
      </Group>
      <Group title="Billing provider">
        <Text label="Provider name" {...field('billing_provider/name')} />
        <Text label="NPI" {...field('billing_provider/npi')} />
        <Text label="Tax ID (EIN)" {...field('billing_provider/tax_id')} />
        <Text label="Address" {...field('billing_provider/address/line1')} />
        <Text label="City" {...field('billing_provider/address/city')} />
        <Text label="State" {...field('billing_provider/address/state')} />
        <Text label="ZIP+4" hint="9 digits" {...field('billing_provider/address/zip_code')} />
      </Group>
      {payers.length > 0 && (
        <Group title="Electronic payer IDs" summary="The ID each payer goes by on a claim file.">
          {payers.map((payer) => (
            <Text
              key={payer.payer_id}
              label={payer.payer_name}
              value={form.payer_ids[payer.payer_id]}
              onChange={(value) => set(`payer_ids/${payer.payer_id}`, value)}
            />
          ))}
        </Group>
      )}
      {facilities.length > 0 && (
        <Group title="Facility ZIP+4" summary="Claim files need 9 digits wherever the service was performed. Leave blank if the address on file already has them.">
          {facilities.map((facility) => (
            <Text
              key={facility.facility_id}
              label={facility.facility_name}
              hint={facility.address}
              value={form.facility_zip_codes[facility.facility_id]}
              onChange={(value) => set(`facility_zip_codes/${facility.facility_id}`, value)}
            />
          ))}
        </Group>
      )}
      <Group title="Clearinghouse" summary="Only for sending from VeriClaim. Leave blank if you send from your own billing system.">
        <Text label="Clearinghouse ID" {...field('receiver/id')} />
        <Text label="Clearinghouse name" {...field('receiver/name')} />
      </Group>
      <fieldset className="space-y-2">
        <legend className="text-sm font-semibold text-gray-900">Kind of file</legend>
        <label className="flex items-start gap-2 text-sm text-gray-800">
          <input type="radio" name="edi-mode" className="mt-0.5" checked={form.mode === 'test'} onChange={() => set('mode', 'test')} />
          <span>
            <span className="font-medium">Test files</span>
            <span className="block text-gray-500">Marked as tests, so they can be tried safely.</span>
          </span>
        </label>
        <label className="flex items-start gap-2 text-sm text-gray-800">
          <input type="radio" name="edi-mode" className="mt-0.5" checked={form.mode === 'production'} onChange={() => set('mode', 'production')} />
          <span>
            <span className="font-medium">Live files</span>
            <span className="block text-gray-500">Marked for real use once everything above is filled in. Try a test file in your billing system first.</span>
          </span>
        </label>
      </fieldset>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          Could not save — {error}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? 'Saving…' : 'Save settings'}
        </button>
        <button type="button" className="btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  )
}

/** The organisation's identifiers for 837 claim files, and whether its files are live yet. */
export default function EdiSettingsCard() {
  const { data, error, reload } = useApi((options) => getEdiSettings(options))
  const payers = useApi((options) => listPayers(options))
  const facilities = useApi((options) => listFacilities(options))
  const [editing, setEditing] = useState(false)

  if (error) {
    return (
      <section className="card p-6">
        <p role="alert" className="text-sm text-red-700">
          Could not load the claim file settings — {error}
        </p>
      </section>
    )
  }
  if (!data) return null

  return (
    <section aria-label="Claim file settings" className="card space-y-4 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-[15px] font-semibold text-gray-900">Claim file settings</h2>
          <p className="text-sm text-gray-500">The identifiers your 837 claim files carry. Files already created don’t change.</p>
        </div>
        {!editing && (
          <button type="button" className="btn-secondary btn-sm" onClick={() => setEditing(true)}>
            Edit settings
          </button>
        )}
      </div>
      <div className="space-y-3">
        <Readiness label="Files for your billing system" mode={data.settings.mode} missing={data.missing_for_handoff} />
        <Readiness label="Files sent from VeriClaim" mode={data.settings.mode} missing={data.missing_for_sending} />
      </div>
      {editing && (
        <SettingsForm
          initial={data.settings}
          payers={(payers.data ?? []).filter((payer) => payer.payer_type !== 'Self-Pay')}
          facilities={(facilities.data ?? []).filter((facility) => facility.status === 'Active')}
          onCancel={() => setEditing(false)}
          onSaved={() => {
            setEditing(false)
            reload()
          }}
        />
      )}
    </section>
  )
}
