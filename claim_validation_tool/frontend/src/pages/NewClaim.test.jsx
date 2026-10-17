import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { mockApi, reply, sentBodies } from '../test/mockApi'
import NewClaim from './NewClaim'

const PATIENT = {
  patient_id: 'PAT000003',
  first_name: 'Donald',
  last_name: 'Davis',
  age: 49,
  gender: 'F',
  primary_payer_id: 'PAY001',
  zip_code: '28205',
  claim_count: 9,
  denial_count: 3,
}

const LISTS = {
  'GET /payers': () => [
    { payer_id: 'PAY001', payer_name: 'Medicare FFS' },
    { payer_id: 'PAY002', payer_name: 'Blue Cross NC' },
  ],
  'GET /departments': () => [{ department_id: 'DEPT02', department_name: 'Internal Medicine' }],
  'GET /providers': () => [
    {
      provider_id: 'PROV001',
      provider_name: 'Dr. Test One',
      credential: 'MD',
      specialty: 'Internal Medicine',
      department_id: 'DEPT02',
      status: 'Active',
    },
  ],
  'GET /facilities': () => [{ facility_id: 'FAC001', facility_name: 'Main Hospital' }],
  'GET /codes/procedures': () => [
    { cpt_code: '99213', description: 'Office visit', standard_charge: 95 },
    { cpt_code: '93000', description: 'ECG', standard_charge: 40 },
  ],
  'GET /codes/diagnoses': () => [{ icd10_code: 'E11.65', description: 'Type 2 diabetes' }],
  'GET /patients': ({ params }) =>
    params.search.toLowerCase().includes('davis')
      ? { items: [PATIENT], total: 1 }
      : { items: [], total: 0 },
}

const CREATED = {
  claim: {
    claim_id: 'CLM0120001',
    patient_id: 'PAT000003',
    patient: PATIENT,
    payer_id: 'PAY001',
    payer: { payer_name: 'Medicare FFS' },
    status: 'Draft',
    is_overdue: false,
    total_charge: 230,
    lines: [{}, {}],
  },
  validation: {
    status: 'warning',
    risk_score: 10,
    risk_factors: [{ label: '1 rule warning', points: 10 }],
    findings: [
      {
        rule_id: 'RULE-008',
        rule_name: 'Non-Clean Claim Review',
        severity: 'warning',
        message: '',
        recommended_action: 'Review the claim',
      },
    ],
  },
}

let user

beforeEach(() => {
  user = userEvent.setup()
})

async function pickPatient() {
  await user.type(screen.getByLabelText('Search registered patients'), 'davis')
  const matches = await screen.findByRole('list', { name: 'Matching patients' })
  await user.click(within(matches).getByRole('button', { name: /Donald Davis/ }))
}

/** Everything but the patient, for a claim with one diagnosis and one line. */
async function fillEncounter() {
  await user.selectOptions(screen.getByLabelText('Rendering provider'), 'PROV001')
  await user.type(screen.getByLabelText('Service date'), '2026-01-05')
  await user.type(screen.getByLabelText('Primary'), 'e11.65')
  await user.selectOptions(screen.getByLabelText('Procedure (CPT)'), '99213')
}

describe('New Claim', () => {
  it('only finds registered patients', async () => {
    mockApi(LISTS)
    render(<NewClaim />)
    await user.type(screen.getByLabelText('Search registered patients'), 'Nobody')
    expect(await screen.findByText(/No registered patient matches “Nobody”/)).toBeInTheDocument()
  })

  it('defaults the payer to the patient’s registered primary and warns on a change', async () => {
    mockApi(LISTS)
    render(<NewClaim />)
    await screen.findByRole('option', { name: 'Medicare FFS' })
    await pickPatient()
    const payer = screen.getByLabelText('Billed payer')
    expect(payer).toHaveValue('PAY001')
    expect(screen.getByText('PAT000003 · 49 F · ZIP 28205 · Medicare FFS')).toBeInTheDocument()

    await user.selectOptions(payer, 'PAY002')
    expect(
      screen.getByText(/Differs from the patient’s registered primary payer/),
    ).toBeInTheDocument()
  })

  it('adds a service line for each new diagnosis', async () => {
    mockApi(LISTS)
    render(<NewClaim />)
    await user.click(screen.getByRole('button', { name: '+ Add diagnosis' }))
    expect(screen.getAllByLabelText('Procedure (CPT)')).toHaveLength(2)
    expect(screen.getAllByLabelText('Diagnosis treated')[1]).toHaveValue('1')
  })

  it('creates the claim and shows its validation', async () => {
    const fetchMock = mockApi({ ...LISTS, 'POST /claims': () => reply(201, CREATED) })
    render(<NewClaim />)
    await screen.findByRole('option', { name: /Dr. Test One/ })
    await pickPatient()
    await fillEncounter()
    // A second diagnosis comes with its own line; give that line a procedure
    await user.click(screen.getByRole('button', { name: '+ Add diagnosis' }))
    await user.type(screen.getByLabelText('Dx 2'), 'i10')
    await user.selectOptions(screen.getAllByLabelText('Procedure (CPT)')[1], '93000')
    await user.type(screen.getAllByLabelText('Charge')[1], '135')
    expect(screen.getByText('$230.00')).toBeInTheDocument() // 95 standard + 135 typed

    await user.click(screen.getByRole('button', { name: 'Create & validate claim' }))

    expect(await screen.findByRole('heading', { name: 'Created CLM0120001' })).toBeInTheDocument()
    const [body] = sentBodies(fetchMock, 'POST /claims')
    expect(body).toMatchObject({
      patient_id: 'PAT000003',
      payer_id: 'PAY001',
      provider_id: 'PROV001',
      diagnoses: ['E11.65', 'I10'],
      lines: [
        { cpt_code: '99213', units: 1, modifier: null, charge_amount: null, icd10_pointer: 'E11.65' },
        { cpt_code: '93000', units: 1, modifier: null, charge_amount: 135, icd10_pointer: 'I10' },
      ],
      service_date: '2026-01-05',
      pa_required: false,
      pa_number: null,
    })
    expect(screen.getByText('Non-Clean Claim Review')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View in Workbench' })).toHaveAttribute(
      'href',
      '#/claims?search=CLM0120001',
    )
    expect(screen.getByRole('button', { name: 'Mark as submitted' })).toBeEnabled()
  })

  it('refuses a diagnosis no service line treats', async () => {
    const fetchMock = mockApi(LISTS)
    render(<NewClaim />)
    await screen.findByRole('option', { name: /Dr. Test One/ })
    await pickPatient()
    await fillEncounter()
    await user.click(screen.getByRole('button', { name: '+ Add diagnosis' }))
    await user.type(screen.getByLabelText('Dx 2'), 'I10')
    await user.selectOptions(screen.getAllByLabelText('Procedure (CPT)')[1], '93000')
    // Point the second line back at the primary diagnosis, leaving I10 untreated
    await user.selectOptions(screen.getAllByLabelText('Diagnosis treated')[1], '0')

    expect(screen.getByText('No service line treats I10 yet.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Create & validate claim' }))
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Every diagnosis needs a service line: add one for I10',
    )
    expect(sentBodies(fetchMock, 'POST /claims')).toEqual([])
  })

  it('shows the server’s reason when the claim is refused', async () => {
    mockApi({
      ...LISTS,
      'POST /claims': () => reply(422, { detail: 'Patient PAT000003 is inactive' }),
    })
    render(<NewClaim />)
    await screen.findByRole('option', { name: /Dr. Test One/ })
    await pickPatient()
    await fillEncounter()
    await user.click(screen.getByRole('button', { name: 'Create & validate claim' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not create the claim — Patient PAT000003 is inactive',
    )
    // The form stays editable so the specialist can correct it
    expect(screen.getByLabelText('Service date')).toBeEnabled()
  })
})
