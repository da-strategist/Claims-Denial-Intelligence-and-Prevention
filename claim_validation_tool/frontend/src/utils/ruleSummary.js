import { CLAIM_TYPES, OPERATOR_SYMBOLS, VALUELESS_OPERATORS } from '../constants'

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
const MONEY_FIELDS = new Set(['total_charge', 'total_allowed', 'total_paid', 'patient_responsibility'])

function formatValue(name, type, value) {
  const number = Number(value)
  switch (type) {
    case 'number':
      if (value === '' || Number.isNaN(number)) return value
      return MONEY_FIELDS.has(name) ? money.format(number) : number.toLocaleString()
    case 'boolean':
      return String(value).toLowerCase() === 'true' ? 'Yes' : 'No'
    case 'enum':
    case 'date':
      return value
    default:
      return `"${value}"`
  }
}

/** e.g. `Total Charge > $30,000.00`. */
export function describeCondition(condition, fields) {
  const field = fields[condition.field]
  const label = field?.label ?? condition.field
  const op = OPERATOR_SYMBOLS[condition.operator] ?? condition.operator
  if (VALUELESS_OPERATORS.has(condition.operator)) return `${label} ${op}`
  return `${label} ${op} ${formatValue(condition.field, field?.type, condition.value)}`
}

/** e.g. `All claims` or `Payers: Aetna, Cigna`. */
export function describeScope(scope, payers, departments) {
  const names = {
    payer: (id) => payers[id]?.payer_name ?? id,
    department: (id) => departments[id]?.department_name ?? id,
    claim_type: (value) => value,
  }
  const prefix = { payer: 'Payers', department: 'Departments', claim_type: 'Claim types' }
  if (!scope || scope.type === 'all') return 'All claims'
  return `${prefix[scope.type]}: ${scope.values.map(names[scope.type]).join(', ')}`
}

/** Options for the scope value picker: [value, label] pairs. */
export function scopeOptions(type, payers, departments) {
  switch (type) {
    case 'payer':
      return Object.values(payers)
        .sort((a, b) => a.payer_name.localeCompare(b.payer_name))
        .map((p) => [p.payer_id, p.payer_name])
    case 'department':
      return Object.values(departments)
        .sort((a, b) => a.department_name.localeCompare(b.department_name))
        .map((d) => [d.department_id, d.department_name])
    case 'claim_type':
      return CLAIM_TYPES.map((t) => [t, t])
    default:
      return []
  }
}
