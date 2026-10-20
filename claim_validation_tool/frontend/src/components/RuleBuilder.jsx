import { useEffect, useId, useRef, useState } from 'react'
import { INPUT_CLASS, RULE_CATEGORIES, SCOPE_TYPES, SEVERITIES } from '../constants'
import { createRule, replaceRule, testRule } from '../services/api'
import { describeScope, scopeOptions } from '../utils/ruleSummary'
import ConditionBuilder from './ConditionBuilder'
import Icon from './Icon'
import Toggle from './Toggle'

const NEW_RULE = {
  name: '',
  description: '',
  category: '',
  severity: 'warning',
  enabled: true,
  recommended_action: '',
  scope: { type: 'all', values: [] },
  conditions: [{ field: 'total_charge', operator: 'greaterThan', value: '' }],
  condition_logic: 'AND',
}

const EDITABLE_FIELDS = Object.keys(NEW_RULE)

function toDraft(rule) {
  if (!rule) return structuredClone(NEW_RULE)
  const draft = Object.fromEntries(EDITABLE_FIELDS.map((key) => [key, structuredClone(rule[key])]))
  draft.conditions = draft.conditions.map((c) => ({ ...c, value: c.value ?? '' }))
  return draft
}

function definitionOf(draft) {
  return { scope: draft.scope, conditions: draft.conditions, condition_logic: draft.condition_logic }
}

function Label({ htmlFor, children, hint }) {
  return (
    <label htmlFor={htmlFor} className="mb-1 block text-sm font-medium text-gray-800">
      {children}
      {hint && <span className="ml-1 font-normal text-gray-400">{hint}</span>}
    </label>
  )
}

function Section({ title, children }) {
  return (
    <section className="space-y-3 border-t border-gray-100 pt-5">
      <h3 className="eyebrow">{title}</h3>
      {children}
    </section>
  )
}

function ScopePicker({ scope, payers, departments, onChange }) {
  const options = scopeOptions(scope.type, payers, departments)
  const toggleValue = (value) => {
    const values = scope.values.includes(value)
      ? scope.values.filter((v) => v !== value)
      : [...scope.values, value]
    onChange({ ...scope, values })
  }
  return (
    <div className="space-y-2">
      <select
        aria-label="Applies to"
        className={INPUT_CLASS}
        value={scope.type}
        onChange={(e) => onChange({ type: e.target.value, values: [] })}
      >
        {SCOPE_TYPES.map((t) => (
          <option key={t.value} value={t.value}>
            {t.label}
          </option>
        ))}
      </select>
      {options.length > 0 && (
        <fieldset className="grid max-h-48 gap-1 overflow-y-auto rounded-xl p-2 ring-1 ring-gray-200/70 sm:grid-cols-2">
          <legend className="sr-only">Choose which ones</legend>
          {options.map(([value, label]) => (
            <label
              key={value}
              className="flex items-center gap-2 rounded px-2 py-1 text-sm text-gray-700 hover:bg-gray-50"
            >
              <input
                type="checkbox"
                className="accent-accent"
                checked={scope.values.includes(value)}
                onChange={() => toggleValue(value)}
              />
              {label}
            </label>
          ))}
        </fieldset>
      )}
    </div>
  )
}

function TestResult({ result }) {
  const share = result.in_scope ? (result.matched / result.in_scope) * 100 : 0
  return (
    <div className="rounded-xl bg-accent-soft p-4 text-sm text-gray-800">
      <p>
        Flags <strong>{result.matched.toLocaleString()}</strong> of{' '}
        {result.in_scope.toLocaleString()} claims in scope ({share.toFixed(1)}%) ·{' '}
        {result.total_claims.toLocaleString()} claims total
      </p>
      {result.sample_claim_ids.length > 0 && (
        <p className="mt-1 break-words text-xs text-gray-500">
          e.g. {result.sample_claim_ids.slice(0, 8).join(', ')}
        </p>
      )}
    </div>
  )
}

/**
 * Slide-in panel to create or edit a rule. `rule` is the rule being edited, or null
 * for a new one. Calls `onSaved(rule)` after a successful save.
 */
export default function RuleBuilder({ rule, fields, payers, departments, onClose, onSaved }) {
  const [draft, setDraft] = useState(() => toDraft(rule))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [test, setTest] = useState({ loading: false, result: null, error: null })
  const titleId = useId()
  const nameRef = useRef(null)
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  })

  // Focus the name field once on open; Escape closes the panel
  useEffect(() => {
    nameRef.current?.focus()
    const onKey = (event) => event.key === 'Escape' && onCloseRef.current()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // Any edit makes a previous test result stale
  const change = (changes) => {
    setDraft((prev) => ({ ...prev, ...changes }))
    setTest({ loading: false, result: null, error: null })
    setError(null)
  }

  const runTest = async () => {
    setTest({ loading: true, result: null, error: null })
    try {
      setTest({ loading: false, result: await testRule(definitionOf(draft)), error: null })
    } catch (err) {
      setTest({ loading: false, result: null, error: err.message })
    }
  }

  const save = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const saved = rule ? await replaceRule(rule.id, draft) : await createRule(draft)
      onSaved(saved)
    } catch (err) {
      setError(err.message)
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-gray-900/20 backdrop-blur-[2px]" onClick={onClose} aria-hidden="true" />
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onSubmit={save}
        className="relative flex h-full w-full max-w-2xl flex-col bg-white shadow-2xl"
      >
        <header className="flex items-start justify-between border-b border-gray-100 px-8 py-5">
          <div>
            <h2 id={titleId} className="text-xl font-semibold tracking-tight text-gray-900">
              {rule ? 'Edit rule' : 'New rule'}
            </h2>
            {rule && <p className="text-xs text-gray-400">{rule.id}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
          >
            <Icon name="close" className="h-5 w-5" />
          </button>
        </header>

        <div className="flex-1 space-y-6 overflow-y-auto px-8 py-6">
          <div className="space-y-3">
            <div>
              <Label htmlFor={`${titleId}-name`}>Name</Label>
              <input
                id={`${titleId}-name`}
                ref={nameRef}
                required
                maxLength={120}
                className={INPUT_CLASS}
                value={draft.name}
                onChange={(e) => change({ name: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor={`${titleId}-desc`} hint="shown on flagged claims">
                Description
              </Label>
              <textarea
                id={`${titleId}-desc`}
                rows={2}
                className={INPUT_CLASS}
                value={draft.description}
                onChange={(e) => change({ description: e.target.value })}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor={`${titleId}-cat`}>Category</Label>
                <select
                  id={`${titleId}-cat`}
                  required
                  className={INPUT_CLASS}
                  value={draft.category}
                  onChange={(e) => change({ category: e.target.value })}
                >
                  <option value="">Select…</option>
                  {RULE_CATEGORIES.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-end gap-3 pb-2">
                <Toggle
                  checked={draft.enabled}
                  onChange={(enabled) => change({ enabled })}
                  label="Enabled"
                />
                <span className="text-sm text-gray-700">
                  {draft.enabled ? 'Enabled' : 'Disabled'}
                </span>
              </div>
            </div>
            <fieldset>
              <legend className="mb-1 text-sm font-medium text-gray-800">Severity</legend>
              <div className="grid grid-cols-3 gap-2">
                {SEVERITIES.map((s) => (
                  <label
                    key={s.value}
                    className={`cursor-pointer rounded-xl border px-3 py-2 text-sm ${draft.severity === s.value ? 'border-accent bg-accent-soft ring-4 ring-accent/15' : 'border-gray-200 hover:bg-gray-50'}`}
                  >
                    <input
                      type="radio"
                      name="severity"
                      value={s.value}
                      className="sr-only"
                      checked={draft.severity === s.value}
                      onChange={() => change({ severity: s.value })}
                    />
                    <span className="block font-medium text-gray-900">{s.label}</span>
                    <span className="block text-xs text-gray-500">{s.hint}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          </div>

          <Section title="Applies to">
            <ScopePicker
              scope={draft.scope}
              payers={payers}
              departments={departments}
              onChange={(scope) => change({ scope })}
            />
          </Section>

          <Section title="Conditions">
            <ConditionBuilder
              conditions={draft.conditions}
              logic={draft.condition_logic}
              fields={fields}
              onChange={(conditions) => change({ conditions })}
              onLogicChange={(condition_logic) => change({ condition_logic })}
            />
          </Section>

          <Section title="Recommended action">
            <textarea
              aria-label="Recommended action"
              rows={2}
              placeholder="What should the biller do when this rule flags a claim?"
              className={INPUT_CLASS}
              value={draft.recommended_action}
              onChange={(e) => change({ recommended_action: e.target.value })}
            />
          </Section>

          <Section title="Test against all claims">
            <p className="text-sm text-gray-500">
              {describeScope(draft.scope, payers, departments)}. Testing doesn't save the rule.
            </p>
            <button
              type="button"
              onClick={runTest}
              disabled={test.loading}
              className="btn-secondary btn-sm"
            >
              {test.loading ? 'Testing…' : 'Test rule'}
            </button>
            {test.result && <TestResult result={test.result} />}
            {test.error && (
              <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
                {test.error}
              </p>
            )}
          </Section>
        </div>

        <footer className="space-y-3 border-t border-gray-100 px-8 py-4">
          {error && (
            <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
              Could not save — {error}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="btn-primary"
            >
              {saving ? 'Saving…' : rule ? 'Save changes' : 'Create rule'}
            </button>
          </div>
        </footer>
      </form>
    </div>
  )
}
