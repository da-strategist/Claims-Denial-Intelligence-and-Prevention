// `color` is the matching chart fill (Tailwind 500 shade)
export const VALIDATION_STATUSES = {
  pass: {
    label: 'Pass',
    icon: '✓',
    style: 'bg-emerald-50 text-emerald-800 border-emerald-200',
    color: '#10b981',
  },
  warning: {
    label: 'Warning',
    icon: '!',
    style: 'bg-amber-50 text-amber-800 border-amber-200',
    color: '#f59e0b',
  },
  error: { label: 'Error', icon: '✕', style: 'bg-red-50 text-red-800 border-red-200', color: '#ef4444' },
  aifix: {
    label: 'AI Fix',
    icon: '✦',
    style: 'bg-violet-50 text-violet-800 border-violet-200',
    color: '#8b5cf6',
  },
}

export const DASHBOARD_PERIODS = [
  { months: 12, label: 'Last 12 months' },
  { months: 6, label: 'Last 6 months' },
  { months: 3, label: 'Last 3 months' },
  { months: '', label: 'All time' },
]

export const EMPTY_FILTERS = {
  search: '',
  status: '',
  payer_id: '',
  claim_type: '',
  is_clean_claim: '',
  missing_prior_auth: '',
  overdue: '',
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
export const FIELD_CLASS =
  'rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 focus:border-red-400 focus:outline-none focus:ring-2 focus:ring-red-100'

export const INPUT_CLASS = `w-full ${FIELD_CLASS}`

export const SUGGESTION_ACTIONS = {
  apply: { label: 'Fix available', style: 'bg-violet-50 text-violet-800 border-violet-200' },
  manual: { label: 'Manual task', style: 'bg-gray-50 text-gray-700 border-gray-200' },
  clarify: { label: 'Needs clarification', style: 'bg-sky-50 text-sky-800 border-sky-200' },
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
