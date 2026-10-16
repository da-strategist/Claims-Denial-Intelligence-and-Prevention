export const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

const compactCurrencyFormat = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  notation: 'compact',
  maximumFractionDigits: 1,
})

/** $1.2M, $45.3K */
export const compactCurrency = (value) => compactCurrencyFormat.format(value)

/** 0.1862 -> "18.6%" */
export const percent = (ratio, digits = 1) => `${(ratio * 100).toFixed(digits)}%`

/** "2025-03" -> "Mar '25" */
export function monthLabel(month) {
  const [year, monthNumber] = month.split('-').map(Number)
  const name = new Date(year, monthNumber - 1).toLocaleString('en-US', { month: 'short' })
  return `${name} '${String(year).slice(2)}`
}

/** "2025-03-01" -> "Mar 1, 2025" (parsed as a calendar date, not UTC midnight) */
export function dateLabel(isoDate) {
  const [year, month, day] = isoDate.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}
