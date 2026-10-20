// `dot` marks the status in tables; `color` is the matching chart fill.
// Green for good, amber for review, red for problems, violet for AI Fix.
export const VALIDATION_STATUSES = {
  pass: { label: 'Pass', dot: 'bg-emerald-500', text: 'text-emerald-700', color: '#10b981' },
  warning: { label: 'Warning', dot: 'bg-amber-500', text: 'text-amber-700', color: '#f5a623' },
  error: { label: 'Error', dot: 'bg-red-500', text: 'text-red-700', color: '#e5484d' },
  aifix: { label: 'AI Fix', dot: 'bg-violet-500', text: 'text-violet-700', color: '#7c5cff' },
}

export const DASHBOARD_PERIODS = [
  { months: '', label: 'All time' },
  { months: 12, label: 'Last 12 months' },
  { months: 6, label: 'Last 6 months' },
  { months: 3, label: 'Last 3 months' },
]

// SAMPLE DATA ONLY — change before going live. The Overview opens on All time because the
// synthetic claims end in December 2025 while claims entered now carry 2026 dates, and
// "Last N months" counts back from the latest service date, so one new claim would move the
// window onto mostly empty months. On real, continuous claims, open on 'Last 12 months' (12)
// and count the window back from today (services/dashboard.py `_periods`). See PHASES.md,
// "Before going live".
export const DEFAULT_DASHBOARD_MONTHS = ''

export const EMPTY_FILTERS = {
  search: '',
  status: '',
  payer_id: '',
  claim_type: '',
  is_clean_claim: '',
  missing_prior_auth: '',
  overdue: '',
  // Set from links (e.g. the dashboard's period); shown as removable chips
  department_id: '',
  service_date_from: '',
  service_date_to: '',
}

export const CLAIM_STATUSES = ['Draft', 'Pending', 'Paid', 'Denied']

export const RULE_CATEGORIES = [
  'Coding',
  'Eligibility',
  'Authorization',
  'Demographics',
  'Billing',
  'Required Fields',
  'Payer-Specific',
]

export const SEVERITIES = [
  { value: 'error', label: 'Error', hint: 'Blocks the claim' },
  { value: 'warning', label: 'Warning', hint: 'Flags for review' },
  { value: 'info', label: 'Info', hint: 'Informational only' },
]

export const OPERATOR_LABELS = {
  isEmpty: 'is empty',
  isNotEmpty: 'is not empty',
  equals: 'equals',
  notEquals: 'does not equal',
  greaterThan: 'is greater than',
  lessThan: 'is less than',
  contains: 'contains',
}

export const OPERATOR_SYMBOLS = {
  isEmpty: 'is empty',
  isNotEmpty: 'is not empty',
  equals: '=',
  notEquals: '≠',
  greaterThan: '>',
  lessThan: '<',
  contains: 'contains',
}

export const VALUELESS_OPERATORS = new Set(['isEmpty', 'isNotEmpty'])

export const SCOPE_TYPES = [
  { value: 'all', label: 'All claims' },
  { value: 'payer', label: 'Specific payers' },
  { value: 'claim_type', label: 'Specific claim types' },
  { value: 'department', label: 'Specific departments' },
]

export const CLAIM_TYPES = ['Professional', 'Institutional']

export const PLACES_OF_SERVICE = [
  { value: '11', label: '11 · Office' },
  { value: '22', label: '22 · Outpatient hospital' },
  { value: '23', label: '23 · Emergency room' },
]

// Without a width, so callers can size it (Tailwind ignores class order when two widths clash)
export const FIELD_CLASS = 'field'

export const INPUT_CLASS = `w-full ${FIELD_CLASS}`

export const SUGGESTION_ACTIONS = {
  apply: { label: 'Fix available', style: 'bg-violet-50 text-violet-700' },
  manual: { label: 'Manual task', style: 'bg-gray-100 text-gray-600' },
  clarify: { label: 'Needs clarification', style: 'bg-accent-soft text-accent' },
}

// Starting question for each topic; the specialist can edit it before asking
export const TOPIC_QUESTIONS = {
  medical_necessity:
    'Do the diagnoses on this claim support medical necessity for its procedures? What documentation is required?',
  ncci_modifiers:
    'Do any NCCI edits or MUE limits apply to the procedures on this claim, and can a modifier be used?',
  payer_prior_auth:
    'What do this payer’s profile and contracts say about these services and prior authorization?',
  appeal: 'Draft appeal wording for this denial based on its CARC/RARC codes and the claim.',
}

export const CLARIFICATION_TOPICS = {
  medical_necessity: 'Medical necessity',
  ncci_modifiers: 'NCCI / modifiers',
  payer_prior_auth: 'Payer prior auth rules',
  appeal: 'Appeal wording',
}
