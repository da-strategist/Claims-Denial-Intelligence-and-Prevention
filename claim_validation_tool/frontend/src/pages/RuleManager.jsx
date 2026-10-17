import { useState } from 'react'
import Icon from '../components/Icon'
import PageHeader, { Notice, Page } from '../components/PageHeader'
import RuleBuilder from '../components/RuleBuilder'
import { SeverityBadge } from '../components/StatusBadge'
import Toggle from '../components/Toggle'
import { FIELD_CLASS, INPUT_CLASS, RULE_CATEGORIES } from '../constants'
import { usePayerLookup } from '../hooks/useClaims'
import { useDepartmentLookup, useRuleFields, useRules } from '../hooks/useRules'
import { deleteRule, updateRule } from '../services/api'
import { describeCondition, describeScope } from '../utils/ruleSummary'

const SEVERITY_ORDER = { error: 0, warning: 1, info: 2 }

function RuleActions({ rule, onEdit, onDelete, busy }) {
  const [confirming, setConfirming] = useState(false)
  if (confirming) {
    return (
      <div className="flex items-center justify-end gap-2 text-sm">
        <span className="text-gray-600">Delete?</span>
        <button className="btn-danger btn-sm" disabled={busy} onClick={() => onDelete(rule)}>
          Delete
        </button>
        <button className="btn-secondary btn-sm" onClick={() => setConfirming(false)}>
          Cancel
        </button>
      </div>
    )
  }
  return (
    <div className="flex items-center justify-end gap-1 text-sm">
      <button
        className="btn-quiet btn-sm"
        onClick={() => onEdit(rule)}
        aria-label={`Edit ${rule.name}`}
      >
        Edit
      </button>
      <button
        className="btn btn-sm text-gray-500 hover:bg-red-50 hover:text-red-700"
        onClick={() => setConfirming(true)}
        aria-label={`Delete ${rule.name}`}
      >
        Delete
      </button>
    </div>
  )
}

function RuleRow({ rule, fields, payers, departments, busy, onToggle, onEdit, onDelete }) {
  return (
    <tr className={`border-b border-gray-100 align-top last:border-0 ${rule.enabled ? '' : 'opacity-60'}`}>
      <td className="px-4 py-5">
        <Toggle
          checked={rule.enabled}
          onChange={(enabled) => onToggle(rule, enabled)}
          label={`${rule.enabled ? 'Disable' : 'Enable'} ${rule.name}`}
          disabled={busy}
        />
      </td>
      <td className="max-w-sm px-4 py-5">
        <div className="text-[15px] font-medium text-gray-900">
          {rule.name}
        </div>
        <div className="text-xs text-gray-400">
          {rule.id} · {rule.category}
        </div>
        {rule.description && <p className="mt-1 text-sm text-gray-600">{rule.description}</p>}
      </td>
      <td className="px-4 py-5">
        <SeverityBadge severity={rule.severity} />
      </td>
      <td className="max-w-xs px-4 py-5 text-sm text-gray-600">
        {describeScope(rule.scope, payers, departments)}
      </td>
      <td className="max-w-sm px-4 py-5">
        <ul className="space-y-1">
          {rule.conditions.map((condition, index) => (
            <li key={index} className="text-sm text-gray-800">
              {index > 0 && (
                <span className="mr-1 text-xs font-medium text-gray-400">
                  {rule.condition_logic}
                </span>
              )}
              <span className="rounded-md bg-gray-100 px-1.5 py-0.5 text-[13px] text-gray-700 [box-decoration-break:clone]">
                {describeCondition(condition, fields)}
              </span>
            </li>
          ))}
        </ul>
      </td>
      <td className="px-4 py-5">
        <RuleActions rule={rule} onEdit={onEdit} onDelete={onDelete} busy={busy} />
      </td>
    </tr>
  )
}

export default function RuleManager() {
  const { data: rules, loading, error, reload } = useRules()
  const fields = useRuleFields()
  const payers = usePayerLookup()
  const departments = useDepartmentLookup()

  const [editing, setEditing] = useState(null) // null = closed, 'new', or a rule
  const [busyId, setBusyId] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [category, setCategory] = useState('')
  const [search, setSearch] = useState('')

  const runAction = async (rule, action) => {
    setBusyId(rule.id)
    setActionError(null)
    try {
      await action()
      reload()
    } catch (err) {
      setActionError(`${rule.name}: ${err.message}`)
    } finally {
      setBusyId(null)
    }
  }

  const term = search.trim().toLowerCase()
  const visible = (rules ?? [])
    .filter((rule) => !category || rule.category === category)
    .filter(
      (rule) =>
        !term ||
        rule.name.toLowerCase().includes(term) ||
        rule.description.toLowerCase().includes(term) ||
        rule.id.toLowerCase().includes(term),
    )
    .sort(
      (a, b) =>
        Number(b.enabled) - Number(a.enabled) ||
        SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity] ||
        a.id.localeCompare(b.id),
    )
  const enabledCount = (rules ?? []).filter((rule) => rule.enabled).length

  return (
    <Page wide>
      <PageHeader
        title="Rules"
        subtitle="Every claim is checked against these rules. Changes apply immediately."
      >
        <button onClick={() => setEditing('new')} className="btn-primary">
          <Icon name="plus" className="h-4 w-4" strokeWidth={2} />
          New rule
        </button>
      </PageHeader>

      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          aria-label="Search rules"
          placeholder="Search rules…"
          className={`${INPUT_CLASS} py-1.5 text-[13px] sm:w-64`}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          aria-label="Category"
          className={`${FIELD_CLASS} py-1.5 text-[13px]`}
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="">All categories</option>
          {RULE_CATEGORIES.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        {rules && (
          <span className="ml-auto text-sm text-gray-500">
            {enabledCount} of {rules.length} rules enabled
          </span>
        )}
      </div>

      {(error || actionError) && (
        <Notice>{error ? `Could not load rules — ${error}` : actionError}</Notice>
      )}

      <div className="card relative overflow-x-auto">
        <table className={`w-full transition-opacity ${loading && rules ? 'opacity-60' : ''}`}>
          <thead>
            <tr className="border-b border-gray-100 text-left text-xs font-medium text-gray-500">
              <th scope="col" className="px-4 py-3">
                On
              </th>
              <th scope="col" className="px-4 py-3">
                Rule
              </th>
              <th scope="col" className="px-4 py-3">
                Severity
              </th>
              <th scope="col" className="px-4 py-3">
                Applies to
              </th>
              <th scope="col" className="px-4 py-3">
                Conditions
              </th>
              <th scope="col" className="px-4 py-3">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {visible.map((rule) => (
              <RuleRow
                key={rule.id}
                rule={rule}
                fields={fields}
                payers={payers}
                departments={departments}
                busy={busyId === rule.id}
                onToggle={(r, enabled) => runAction(r, () => updateRule(r.id, { enabled }))}
                onEdit={setEditing}
                onDelete={(r) => runAction(r, () => deleteRule(r.id))}
              />
            ))}
            {!rules && loading && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-sm text-gray-500">
                  Loading rules…
                </td>
              </tr>
            )}
            {rules && visible.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-sm text-gray-500">
                  {rules.length ? 'No rules match.' : 'No rules yet — create one to get started.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {editing && (
        <RuleBuilder
          rule={editing === 'new' ? null : editing}
          fields={fields}
          payers={payers}
          departments={departments}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            reload()
          }}
        />
      )}
    </Page>
  )
}
