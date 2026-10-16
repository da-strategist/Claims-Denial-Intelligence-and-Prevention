export const VALIDATION_STATUSES = {
  pass: { label: 'Pass', icon: '✓', style: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
  warning: { label: 'Warning', icon: '!', style: 'bg-amber-50 text-amber-800 border-amber-200' },
  error: { label: 'Error', icon: '✕', style: 'bg-red-50 text-red-800 border-red-200' },
  aifix: { label: 'AI Fix', icon: '✦', style: 'bg-violet-50 text-violet-800 border-violet-200' },
}

export const EMPTY_FILTERS = {
  search: '',
  status: '',
  payer_id: '',
  claim_type: '',
  is_clean_claim: '',
  missing_prior_auth: '',
}

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

// Without a width, so callers can size it (Tailwind ignores class order when two widths clash)
export const FIELD_CLASS =
  'rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 focus:border-red-400 focus:outline-none focus:ring-2 focus:ring-red-100'

export const INPUT_CLASS = `w-full ${FIELD_CLASS}`

export const SUGGESTION_ACTIONS = {
  apply: { label: 'Fix available', style: 'bg-violet-50 text-violet-800 border-violet-200' },
  manual: { label: 'Manual task', style: 'bg-gray-50 text-gray-700 border-gray-200' },
  clarify: { label: 'Needs clarification', style: 'bg-sky-50 text-sky-800 border-sky-200' },
}

export const CLARIFICATION_TOPICS = {
  medical_necessity: 'Medical necessity',
  ncci_modifiers: 'NCCI / modifiers',
  payer_prior_auth: 'Payer prior auth rules',
  appeal: 'Appeal wording',
}
