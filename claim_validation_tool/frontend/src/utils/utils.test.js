import { describe, expect, it } from 'vitest'
import { lineCharge, unsupportedDiagnoses } from './claimEntry'
import { compactCurrency, dateLabel, monthLabel, percent } from './format'
import { hashPath, routeHref } from './route'
import { describeCondition, describeScope, scopeOptions } from './ruleSummary'

describe('claim entry', () => {
  const procedures = { 99213: { standard_charge: 95 } }

  it('uses a typed charge, else standard charge × units', () => {
    expect(lineCharge({ cpt_code: '99213', units: '2', charge: '' }, procedures)).toBe(190)
    expect(lineCharge({ cpt_code: '99213', units: '2', charge: '150' }, procedures)).toBe(150)
    expect(lineCharge({ cpt_code: '', units: '1', charge: '' }, procedures)).toBe(0)
    expect(lineCharge({ cpt_code: '99213', units: '', charge: '' }, procedures)).toBe(0)
  })

  it('finds diagnoses no line points at', () => {
    const lines = [{ dx: 0 }, { dx: 2 }]
    expect(unsupportedDiagnoses(['E11.65', 'I10', 'J18.9', 'K21.0'], lines)).toEqual([
      { code: 'I10', index: 1 },
      { code: 'K21.0', index: 3 },
    ])
  })
})

describe('formatting', () => {
  it('formats money, percentages, and dates', () => {
    expect(compactCurrency(1_234_567)).toBe('$1.2M')
    expect(percent(0.1862)).toBe('18.6%')
    expect(monthLabel('2025-03')).toBe("Mar '25")
    // A calendar date, not shifted by the time zone
    expect(dateLabel('2025-03-01')).toBe('Mar 1, 2025')
  })
})

describe('routes', () => {
  it('splits and builds hash routes with queries', () => {
    expect(hashPath('#/claims?search=CLM1')).toBe('#/claims')
    expect(routeHref('#/claims', { search: 'CLM0120001' })).toBe('#/claims?search=CLM0120001')
    expect(routeHref('#/claims', {})).toBe('#/claims')
  })
})

describe('rule summaries', () => {
  const fields = {
    total_charge: { label: 'Total Charge', type: 'number' },
    pa_obtained: { label: 'Prior Auth Obtained', type: 'boolean' },
    primary_icd10: { label: 'Primary ICD-10', type: 'string' },
  }
  const payers = {
    PAY002: { payer_id: 'PAY002', payer_name: 'Blue Cross NC' },
    PAY001: { payer_id: 'PAY001', payer_name: 'Aetna' },
  }

  it('describes conditions by field type', () => {
    const summary = (condition) => describeCondition(condition, fields)
    expect(summary({ field: 'total_charge', operator: 'greaterThan', value: '30000' })).toBe(
      'Total Charge > $30,000.00',
    )
    expect(summary({ field: 'pa_obtained', operator: 'equals', value: 'false' })).toBe(
      'Prior Auth Obtained = No',
    )
    expect(summary({ field: 'primary_icd10', operator: 'isEmpty', value: '' })).toBe(
      'Primary ICD-10 is empty',
    )
    // Unknown fields fall back to the raw name
    expect(summary({ field: 'mystery', operator: 'equals', value: 'x' })).toBe('mystery = "x"')
  })

  it('describes scopes and sorts scope options by name', () => {
    expect(describeScope({ type: 'all', values: [] }, payers, {})).toBe('All claims')
    expect(describeScope({ type: 'payer', values: ['PAY002', 'PAY009'] }, payers, {})).toBe(
      'Payers: Blue Cross NC, PAY009',
    )
    expect(scopeOptions('payer', payers, {})).toEqual([
      ['PAY001', 'Aetna'],
      ['PAY002', 'Blue Cross NC'],
    ])
  })
})
