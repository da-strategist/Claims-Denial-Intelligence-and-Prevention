import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { mockApi, reply, sentBodies } from '../test/mockApi'
import { AuthContext } from '../hooks/useAuth'
import NewClaimPage from './NewClaim'

// The page is only offered to roles that can enter claims
const BILLER = { user: { username: 'biller1', permissions: ['claims:read', 'claims:write', 'patients:read'] } }
const NewClaim = () => (
  <AuthContext.Provider value={BILLER}>
    <NewClaimPage />
  </AuthContext.Provider>
)

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
  'GET /drafts': () => [],
  'GET /patients/PAT000003/registration': () => REGISTRATION,
  'GET /claims': () => ({ items: [], total: 0, page: 1, pages: 0, page_size: 100 }),
  'POST /validate': () => [],
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

const REGISTRATION = {
  patient_id: 'PAT000003',
  birth_date: '1977-03-14',
  sex: 'F',
  address: { line1: '12 Oak St', line2: null, city: 'Charlotte', state: 'NC', zip_code: '28205' },
  policies: { PAY001: { member_id: 'POL001123456789', group_number: null, relationship: 'self' } },
  source: 'sample',
}

/** What the form sends once the registration has filled it in. */
const BILLING = {
  patient_birth_date: '1977-03-14',
  patient_address: { line1: '12 Oak St', line2: null, city: 'Charlotte', state: 'NC', zip_code: '28205' },
  policy: { member_id: 'POL001123456789', group_number: null, relationship: 'self' },
  other_policies: [],
  institutional: null,
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

/** The created claim as the opened view loads it: detail plus fixes and validation. */
const OPENED = {
  'GET /claims/CLM0120001': () => ({ ...CREATED.claim, lines: [], denials: [], service_date: '2026-01-05' }),
  'GET /aifix/CLM0120001': () => ({ suggestions: [], corrections: [], validation: CREATED.validation }),
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
    const fetchMock = mockApi({ ...LISTS, ...OPENED, 'POST /claims': () => reply(201, CREATED) })
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
      billing: BILLING,
    })
    // It opens right here with its findings; its warning blocks submission until resolved
    expect(await screen.findByText('Non-Clean Claim Review')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mark as submitted' })).toBeDisabled()
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

  describe('saved drafts', () => {
    const SAVED = {
      id: 'DRF-0000abcd',
      created_by: 'biller1',
      created_at: '2026-10-17T09:00:00Z',
      updated_by: 'biller1',
      updated_at: '2026-10-17T09:00:00Z',
      expires_at: '2026-11-16T09:00:00Z',
    }
    const ROW = {
      id: SAVED.id,
      patient_id: 'PAT000003',
      patient_name: 'Donald Davis',
      lines: 1,
      updated_by: 'biller1',
      updated_at: SAVED.updated_at,
      expires_at: SAVED.expires_at,
    }

    it('saves an incomplete form without validating it, then saves over it', async () => {
      const fetchMock = mockApi({
        ...LISTS,
        'POST /drafts': ({ body }) => reply(201, { ...SAVED, form: body }),
        'PUT /drafts/DRF-0000abcd': ({ body }) => ({ ...SAVED, form: body }),
      })
      render(<NewClaim />)
      await pickPatient()
      // Nothing else filled in: the form's required fields don't stop a draft
      await user.click(screen.getByRole('button', { name: 'Save draft' }))
      expect(await screen.findByText(/Saved at .* not validated/)).toBeInTheDocument()
      const [saved] = sentBodies(fetchMock, 'POST /drafts')
      expect(saved).toMatchObject({ patient_id: 'PAT000003', payer_id: 'PAY001', provider_id: '', service_date: '' })
      expect(sentBodies(fetchMock, 'POST /claims')).toEqual([])

      await user.type(screen.getByLabelText('Primary'), 'e11')
      await user.click(screen.getByRole('button', { name: 'Save draft' }))
      await waitFor(() => expect(sentBodies(fetchMock, 'PUT /drafts/DRF-0000abcd')).toHaveLength(1))
      expect(sentBodies(fetchMock, 'PUT /drafts/DRF-0000abcd')[0].diagnoses).toEqual(['E11'])
    })

    it('reopens a saved draft and removes it once its claim is created', async () => {
      const form = {
        patient_id: 'PAT000003',
        payer_id: 'PAY001',
        other_payer_ids: [],
        provider_id: 'PROV001',
        facility_id: 'FAC001',
        diagnoses: ['E11.65'],
        lines: [{ cpt_code: '99213', units: '1', modifier: '', charge: '', dx: 0 }],
        claim_type: 'Professional',
        place_of_service: '11',
        service_date: '2026-01-05',
        submission_date: '2026-01-06',
        pa_required: false,
        pa_obtained: false,
        pa_number: '',
        billing: {
          patient_birth_date: '1977-03-14',
          patient_address: { line1: '12 Oak St', line2: '', city: 'Charlotte', state: 'NC', zip_code: '28205' },
          policy: { member_id: 'POL001123456789', group_number: '', relationship: 'self', first_name: '', last_name: '', birth_date: '', sex: '' },
          other_policies: [],
          institutional: { type_of_bill: '131', admission_type: '3', admission_source: '1', patient_status: '01' },
        },
      }
      let drafts = [ROW]
      const fetchMock = mockApi({
        ...LISTS,
        'GET /drafts': () => drafts,
        'GET /drafts/DRF-0000abcd': () => ({ ...SAVED, form, patient: PATIENT }),
        'DELETE /drafts/DRF-0000abcd': () => {
          drafts = []
          return reply(204)
        },
        'POST /claims': () => reply(201, CREATED),
        ...OPENED,
      })
      render(<NewClaim />)
      await screen.findByRole('option', { name: /Dr. Test One/ })
      const panel = await screen.findByRole('complementary', { name: 'Drafts' })
      await user.click(await within(panel).findByRole('button', { name: 'Open saved draft: Donald Davis' }))

      await waitFor(() => expect(screen.getByLabelText('Rendering provider')).toHaveValue('PROV001'))
      expect(screen.getByLabelText('Service date')).toHaveValue('2026-01-05')
      expect(screen.getByLabelText('Procedure (CPT)')).toHaveValue('99213')

      await user.click(screen.getByRole('button', { name: 'Create & validate claim' }))
      expect(await screen.findByRole('heading', { name: 'Created CLM0120001' })).toBeInTheDocument()
      expect(sentBodies(fetchMock, 'POST /claims')[0]).toMatchObject({ patient_id: 'PAT000003', diagnoses: ['E11.65'] })
      await waitFor(() =>
        expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(true),
      )
    })
  })
})

describe('draft claims in the Drafts panel', () => {
  it('lists unsubmitted claims for anyone to open and finish', async () => {
    const draftClaim = { ...CREATED.claim, service_date: '2026-01-05' }
    mockApi({
      ...LISTS,
      ...OPENED,
      'GET /claims': ({ params }) => {
        expect(params.status).toBe('Draft')
        return { items: [draftClaim], total: 1, page: 1, pages: 1, page_size: 100 }
      },
      'POST /validate': () => [{ claim_id: 'CLM0120001', status: 'warning', risk_score: 10, findings: [], risk_factors: [] }],
    })
    render(<NewClaim />)
    const panel = await screen.findByRole('complementary', { name: 'Drafts' })
    const row = await within(panel).findByRole('button', { name: 'Open draft claim CLM0120001' })
    // Validation results arrive after the list
    await waitFor(() => expect(row).toHaveTextContent('Warning'))
    expect(row).toHaveTextContent('Medicare FFS')

    await user.click(row)
    expect(await screen.findByRole('heading', { name: 'CLM0120001' })).toBeInTheDocument()
    expect(await screen.findByText('Non-Clean Claim Review')).toBeInTheDocument()
    expect(row).toHaveAttribute('aria-current', 'true')

    // Back to an empty form
    await user.click(screen.getByRole('button', { name: 'New claim' }))
    expect(screen.getByRole('button', { name: 'Create & validate claim' })).toBeInTheDocument()
  })
})

describe('billing details for the 837', () => {
  it('fills the patient’s registered details and policy when they’re selected', async () => {
    mockApi(LISTS)
    render(<NewClaim />)
    await screen.findByRole('option', { name: 'Medicare FFS' })
    await pickPatient()
    expect(await screen.findByLabelText('Date of birth')).toHaveValue('1977-03-14')
    expect(screen.getByLabelText('Street address')).toHaveValue('12 Oak St')
    expect(screen.getByLabelText('ZIP code')).toHaveValue('28205')
    expect(screen.getByLabelText('Medicare FFS member ID')).toHaveValue('POL001123456789')
    expect(screen.getByText(/registration \(sample details\)/)).toBeInTheDocument()

    // A payer without a registered policy starts blank
    await user.selectOptions(screen.getByLabelText('Billed payer'), 'PAY002')
    expect(screen.getByLabelText('Blue Cross NC member ID')).toHaveValue('')
  })

  it('asks for the policy holder when it isn’t the patient', async () => {
    mockApi(LISTS)
    render(<NewClaim />)
    await screen.findByRole('option', { name: 'Medicare FFS' })
    await pickPatient()
    await screen.findByLabelText('Medicare FFS member ID')
    expect(screen.queryByLabelText('Holder first name')).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Patient is the policy holder’s'), 'spouse')
    expect(screen.getByLabelText('Holder first name')).toBeRequired()
    expect(screen.getByLabelText('Holder date of birth')).toBeRequired()
  })

  it('sends UB-04 codes and revenue codes on institutional claims', async () => {
    const fetchMock = mockApi({ ...LISTS, ...OPENED, 'POST /claims': () => reply(201, CREATED) })
    render(<NewClaim />)
    await screen.findByRole('option', { name: /Dr. Test One/ })
    await pickPatient()
    await screen.findByLabelText('Medicare FFS member ID')
    await fillEncounter()
    expect(screen.queryByLabelText('Type of bill')).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Claim type'), 'Institutional')
    expect(screen.getByLabelText('Type of bill')).toHaveValue('131')
    await user.type(screen.getByLabelText('Revenue code'), '0510')

    await user.click(screen.getByRole('button', { name: 'Create & validate claim' }))
    await screen.findByRole('heading', { name: 'Created CLM0120001' })
    const [body] = sentBodies(fetchMock, 'POST /claims')
    expect(body.lines[0].revenue_code).toBe('0510')
    expect(body.billing.institutional).toEqual({
      type_of_bill: '131',
      admission_type: '3',
      admission_source: '1',
      patient_status: '01',
    })
  })
})
