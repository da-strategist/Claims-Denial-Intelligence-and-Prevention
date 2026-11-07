// Synthetic claims for the website's interactive demo. No real patients, providers or
// payer data: identifiers are invented and marked DEMO. Rule names, the coverage policy and
// the correction wording mirror the app's own rules and reference tables, so the demo shows
// what the product does, not more.

/** The checks the demo walks through, in order. */
export const CHECKS = [
  { key: 'fields', label: 'Required fields' },
  { key: 'auth', label: 'Prior authorization' },
  { key: 'ncci', label: 'NCCI procedure pairs' },
  { key: 'mue', label: 'MUE unit limits' },
  { key: 'coverage', label: 'Coverage policy (LCD/NCD)' },
  { key: 'payer', label: 'Payer-specific rules' },
]

const line = (cpt, description, dx, units, charge, modifier = '') => ({ cpt, description, dx, units, charge, modifier })

export const DEMO_CLAIMS = [
  {
    id: 'DEMO-2041',
    summary: 'Upper GI endoscopy',
    payer: 'Medicare',
    patient: 'Synthetic patient 0412',
    provider: 'General surgery',
    serviceDate: 'Nov 4, 2026',
    priorAuth: 'Not required',
    diagnoses: ['R10.9'],
    lines: [line('43239', 'Upper GI endoscopy with biopsy', 'R10.9', 1, 1800)],
    issue: {
      check: 'coverage',
      rule: 'Diagnosis Not Covered (LCD/NCD)',
      field: { line: 0, column: 'dx' },
      explanation:
        'Line 1 (CPT 43239) points to R10.9, unspecified abdominal pain. The Upper GI Endoscopy coverage policy (LCD-L33631) covers this procedure only for K21.0, K25.9, K92.1, R11.10 and R13.10.',
      fix: 'The provider’s notes document GERD with esophagitis (K21.0), which is on the covered list.',
      action: 'Apply K21.0',
      applied: 'Diagnosis changed to K21.0',
      apply: (claim) => ({
        ...claim,
        diagnoses: ['K21.0'],
        lines: claim.lines.map((l) => ({ ...l, dx: 'K21.0' })),
      }),
    },
  },
  {
    id: 'DEMO-2042',
    summary: 'Brain MRI',
    payer: 'Humana MA',
    patient: 'Synthetic patient 0587',
    provider: 'Radiology',
    serviceDate: 'Nov 5, 2026',
    priorAuth: 'Required · not on file',
    diagnoses: ['G43.909'],
    lines: [line('70553', 'MRI brain with and without contrast', 'G43.909', 1, 1200)],
    issue: {
      check: 'auth',
      rule: 'Missing Prior Authorization',
      field: { header: 'priorAuth' },
      explanation:
        'This payer requires prior authorization for a brain MRI, and none is recorded on the claim. Without it, the claim is denied.',
      fix: 'The payer portal shows an approved authorization for this date of service: HUM-DEMO-55102.',
      action: 'Add authorization',
      applied: 'Authorization HUM-DEMO-55102 added',
      apply: (claim) => ({ ...claim, priorAuth: 'Obtained · HUM-DEMO-55102' }),
    },
  },
  {
    id: 'DEMO-2043',
    summary: 'Physical therapy',
    payer: 'NC Medicaid',
    patient: 'Synthetic patient 0236',
    provider: 'Physical medicine',
    serviceDate: 'Nov 5, 2026',
    priorAuth: 'Not required',
    diagnoses: ['M54.5'],
    lines: [
      line('97110', 'Therapeutic exercises', 'M54.5', 2, 130),
      line('97140', 'Manual therapy techniques', 'M54.5', 2, 140),
    ],
    issue: {
      check: 'ncci',
      rule: 'NCCI Procedure-to-Procedure Edit',
      field: { line: 1, column: 'modifier' },
      explanation:
        'CPT 97140 on line 2 is bundled with 97110 on the same day. Payers deny it unless a modifier shows it was a distinct service.',
      fix: 'The therapy notes record manual therapy in a separate session, so modifier XU is supported. Without that documentation, the line would be removed instead.',
      action: 'Add modifier XU',
      applied: 'Modifier XU added to line 2',
      apply: (claim) => ({
        ...claim,
        lines: claim.lines.map((l, i) => (i === 1 ? { ...l, modifier: 'XU' } : l)),
      }),
    },
  },
  {
    id: 'DEMO-2044',
    summary: 'Office visit',
    payer: 'Blue Cross NC',
    patient: 'Synthetic patient 0198',
    provider: 'Internal medicine',
    serviceDate: 'Nov 6, 2026',
    priorAuth: 'Not required',
    diagnoses: ['I10', 'E78.5'],
    lines: [
      line('99214', 'Office visit, established, moderate', 'I10', 1, 150),
      line('80061', 'Lipid panel', 'E78.5', 1, 50),
    ],
    issue: null,
  },
]

export const totalCharge = (claim) => claim.lines.reduce((sum, l) => sum + l.units * l.charge, 0)
