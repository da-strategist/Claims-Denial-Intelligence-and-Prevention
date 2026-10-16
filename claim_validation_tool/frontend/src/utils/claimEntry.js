// Limits match the backend (ClaimCreate)
export const MAX_DIAGNOSES = 12
export const MAX_OTHER_PAYERS = 2

/** Charge to show and send: what was typed, else standard charge × units. */
export function lineCharge(line, procedures) {
  if (line.charge !== '') return Number(line.charge)
  const standard = procedures[line.cpt_code]?.standard_charge
  return standard === undefined ? 0 : standard * (Number(line.units) || 0)
}

/** Diagnoses (by position) that no service line points at. */
export function unsupportedDiagnoses(diagnoses, lines) {
  const treated = new Set(lines.map((line) => line.dx))
  return diagnoses.map((code, index) => ({ code, index })).filter(({ index }) => !treated.has(index))
}
