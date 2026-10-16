// Workflow diagram and integration architecture cards for the (conceptual) JAB Audit page

const INTEGRATION_STATUSES = {
  live: { label: 'Live', style: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
  proposed: { label: 'Proposed', style: 'bg-violet-50 text-violet-800 border-violet-200' },
  partial: { label: 'Partial', style: 'bg-sky-50 text-sky-800 border-sky-200' },
  needed: { label: 'Needed', style: 'bg-amber-50 text-amber-800 border-amber-200' },
}

function IntegrationStatus({ status }) {
  const { label, style } = INTEGRATION_STATUSES[status]
  return (
    <span
      className={`inline-flex whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-semibold ${style}`}
    >
      {label}
    </span>
  )
}

const WORKFLOW_STEPS = [
  {
    title: 'Pre-submission validation',
    owner: 'ClaustraRCM',
    status: 'live',
    description: 'Every claim is checked against the rules and scored for denial risk.',
    href: '#/claims',
  },
  {
    title: 'AI Fix & correction',
    owner: 'ClaustraRCM',
    status: 'live',
    description: 'Billing specialists apply suggested fixes and re-validate before submission.',
    href: '#/claims',
  },
  {
    title: 'Submission & adjudication',
    owner: 'Clearinghouse · Payer',
    status: 'needed',
    description: '837 claims out, 835 remittance back. Sample data stands in for this today.',
  },
  {
    title: 'Claim handoff',
    owner: 'ClaustraRCM → JAB Audit',
    status: 'proposed',
    description: 'Adjudicated claims sent nightly with contract rates and validation context.',
    contract: 'claim-handoff',
  },
  {
    title: 'Underpayment audit & recovery',
    owner: 'JAB Audit',
    status: 'proposed',
    description: 'Payments compared with contract terms; variances appealed and tracked.',
    contract: 'underpayment-findings',
  },
  {
    title: 'Feedback into rules',
    owner: 'JAB Audit → Rule Manager',
    status: 'proposed',
    description: 'Recurring underpayment patterns become draft pre-submission rules.',
    contract: 'rule-suggestions',
  },
]

function StepLink({ step }) {
  if (step.href) {
    return (
      <a href={step.href} className="text-xs font-medium text-red-700 hover:underline">
        Open in app →
      </a>
    )
  }
  if (step.contract) {
    // Scroll instead of linking: the URL hash is the page route
    return (
      <button
        type="button"
        onClick={() =>
          document
            .getElementById(`contract-${step.contract}`)
            ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
        className="text-xs font-medium text-violet-700 hover:underline"
      >
        View contract ↓
      </button>
    )
  }
  return null
}

export function WorkflowDiagram() {
  return (
    <div>
      <ol className="grid grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {WORKFLOW_STEPS.map((step, index) => (
          <li
            key={step.title}
            className="relative flex flex-col gap-1.5 rounded-xl border border-gray-100 bg-white p-4 shadow-sm"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gray-900 text-xs font-bold text-white">
                {index + 1}
              </span>
              <IntegrationStatus status={step.status} />
            </div>
            <h3 className="text-sm font-semibold text-gray-900">{step.title}</h3>
            <div className="text-xs font-medium text-gray-500">{step.owner}</div>
            <p className="text-sm text-gray-600">{step.description}</p>
            <div className="mt-auto pt-1">
              <StepLink step={step} />
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-3 flex items-start gap-2 rounded-lg bg-gray-100 px-3 py-2 text-sm text-gray-700">
        <span aria-hidden="true">↺</span>
        Step 6 closes the loop: what JAB Audit recovers after payment becomes a rule that
        prevents the same underpayment before the next claim is submitted.
      </p>
    </div>
  )
}

const SYSTEMS = [
  {
    name: 'ClaustraRCM Validation API',
    status: 'live',
    role: 'Rules engine, risk scoring, AI Fix, and the executive dashboard.',
    interface: 'REST · /api/*',
    exchanges: ['Sends: claim handoff with validation context', 'Receives: findings, recovery, rule drafts'],
  },
  {
    name: 'JAB Audit',
    status: 'proposed',
    role: 'Detects underpayments against contract terms, files appeals, tracks recovery.',
    interface: 'REST + HMAC-signed webhooks',
    exchanges: ['Receives: adjudicated claims', 'Sends: findings, recovery status, rule suggestions'],
  },
  {
    name: 'Clearinghouse',
    status: 'needed',
    role: 'Submits claims to payers and returns remittance and status.',
    interface: 'X12 EDI · 837, 835, 276/277',
    exchanges: ['835 remittance triggers the nightly handoff'],
  },
  {
    name: 'EHR / Practice management',
    status: 'needed',
    role: 'Source of encounters, charges, and claims. Synthetic CSVs stand in today.',
    interface: 'HL7 FHIR or batch extract',
    exchanges: ['Claims and lines in; corrected fields written back'],
  },
  {
    name: 'Contract & fee schedule repository',
    status: 'partial',
    role: 'Contracted rates that both systems price against.',
    interface: 'Shared reference data',
    exchanges: [
      'Today: one rate per payer and CPT category',
      'Needs effective-dated, CPT-level rates; the sample allowed amounts don’t follow contract rates yet',
    ],
  },
  {
    name: 'Security & compliance',
    status: 'needed',
    role: 'Business associate agreement, TLS, signed webhooks, audit log.',
    interface: 'Cross-cutting',
    exchanges: ['Payloads carry IDs and amounts only — HIPAA minimum necessary'],
  },
]

export function ArchitectureCards() {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      {SYSTEMS.map((system) => (
        <div
          key={system.name}
          className="flex flex-col gap-2 rounded-xl border border-gray-100 bg-white p-4 shadow-sm"
        >
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-semibold text-gray-900">{system.name}</h3>
            <IntegrationStatus status={system.status} />
          </div>
          <p className="text-sm text-gray-600">{system.role}</p>
          <div className="font-mono text-xs text-gray-500">{system.interface}</div>
          <ul className="space-y-1 text-sm text-gray-700">
            {system.exchanges.map((item) => (
              <li key={item} className="flex gap-2">
                <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-gray-400" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}
