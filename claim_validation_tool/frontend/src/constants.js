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
