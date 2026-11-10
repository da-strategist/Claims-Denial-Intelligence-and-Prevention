import { useRef, useState } from 'react'
import Icon from '../../components/Icon'
import ClaimDemo, { StatusPill } from '../ClaimDemo'
import { Link } from '../Link'

function Eyebrow({ children, inverse = false }) {
  return (
    <div className={`text-xs font-semibold tracking-[0.14em] uppercase ${inverse ? 'text-sky-300' : 'text-accent'}`}>{children}</div>
  )
}

function SectionHeading({ eyebrow, title, children, inverse = false, id }) {
  return (
    <div className="mx-auto max-w-3xl text-center">
      {eyebrow && <Eyebrow inverse={inverse}>{eyebrow}</Eyebrow>}
      <h2
        id={id}
        className={`mt-3 text-3xl font-semibold tracking-tight text-balance sm:text-[2.6rem] sm:leading-[1.1] ${
          inverse ? 'text-white' : 'text-gray-900'
        }`}
      >
        {title}
      </h2>
      {children && (
        <p className={`mt-4 text-lg leading-relaxed text-pretty ${inverse ? 'text-slate-300' : 'text-gray-600'}`}>{children}</p>
      )}
    </div>
  )
}

/* --- Hero ------------------------------------------------------------------------- */

function Hero() {
  return (
    <section aria-labelledby="hero-title" className="relative overflow-hidden">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 -top-40 h-[36rem] bg-[radial-gradient(60%_60%_at_50%_0%,rgba(10,108,224,0.12),transparent)]"
      />
      <div className="relative mx-auto max-w-6xl px-5 pt-14 pb-10 sm:px-8 sm:pt-20">
        <div className="mx-auto max-w-3xl text-center">
          <p className="inline-flex items-center gap-2 rounded-full bg-white px-3.5 py-1.5 text-xs font-medium text-gray-700 shadow-sm ring-1 ring-gray-200">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-green-500" />
            Working Product <span className="text-gray-300">|</span> Early Hospital Pilot Phase
          </p>
          <h1
            id="hero-title"
            className="mt-6 text-4xl font-semibold tracking-tight text-balance text-gray-900 sm:text-6xl sm:leading-[1.04]"
          >
            Catch Claim Errors Before They Become Costly Rework.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-pretty text-gray-600 sm:text-xl">
            VeriClaim helps hospital billing teams validate claims before submission, identify issues that need attention, and
            correct errors through a clear, streamlined workflow.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link href="/#demo" className="btn-primary px-6 py-3 text-base">
              Explore the Demo
            </Link>
            <Link href="/pilot" className="btn-secondary px-6 py-3 text-base">
              Request a Pilot
            </Link>
          </div>
        </div>
        <div id="demo" tabIndex={-1} className="mt-14 scroll-mt-24 focus:outline-none sm:mt-16" aria-label="Interactive claims validation demo">
          <ClaimDemo />
          <p className="mt-4 text-center text-sm text-gray-500">
            Pick a sample claim, validate it, correct what’s flagged, and take it through to Send. Everything here runs in your
            browser on synthetic data.
          </p>
        </div>
      </div>
    </section>
  )
}

/* --- Three steps ------------------------------------------------------------------ */

function Flow({ vertical = false }) {
  // A quiet dashed connector; it drifts only where motion is welcome
  return (
    <span
      aria-hidden="true"
      className={`block shrink-0 motion-safe:animate-[site-flow_1.2s_linear_infinite] ${
        vertical ? 'mx-auto h-6 w-px' : 'h-px w-full'
      }`}
      style={{
        backgroundImage: vertical
          ? 'linear-gradient(to bottom, rgba(125,211,252,0.7) 50%, transparent 50%)'
          : 'linear-gradient(to right, rgba(125,211,252,0.7) 50%, transparent 50%)',
        backgroundSize: vertical ? '1px 8px' : '8px 1px',
      }}
    />
  )
}

function StepPanel({ number, label, title, children, visual }) {
  return (
    <li className="flex flex-col rounded-[1.5rem] bg-navy-soft/70 p-5 ring-1 ring-white/10 sm:p-6">
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm text-sky-300">{number}</span>
        <span className="text-xs font-semibold tracking-[0.18em] text-white uppercase">{label}</span>
      </div>
      <h3 className="mt-4 text-2xl font-semibold tracking-tight text-white">{title}</h3>
      <p className="mt-2 text-[15px] leading-relaxed text-slate-300">{children}</p>
      <div className="mt-6 flex-1">{visual}</div>
    </li>
  )
}

function LoadVisual() {
  const sources = [
    { name: 'API', detail: 'POST /api/v1/claims', icon: 'loop' },
    { name: 'File upload', detail: 'CSV · Excel · 837', icon: 'upload' },
    { name: 'Manual entry', detail: 'New claim form', icon: 'plus' },
  ]
  return (
    <div aria-hidden="true" className="flex h-full flex-col">
      <div className="grid grid-cols-3 gap-2">
        {sources.map((s) => (
          <div key={s.name} className="rounded-xl bg-white/5 p-2.5 text-center ring-1 ring-white/10">
            <Icon name={s.icon} className="mx-auto h-4 w-4 text-sky-300" />
            <div className="mt-1.5 text-xs font-semibold text-white">{s.name}</div>
            <div className="mt-0.5 truncate font-mono text-[10px] text-slate-400">{s.detail}</div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-3">
        <Flow vertical />
        <Flow vertical />
        <Flow vertical />
      </div>
      <div className="rounded-xl bg-white p-3 text-center shadow-lg">
        <div className="text-xs font-semibold text-gray-900">One validation workspace</div>
        <div className="mt-0.5 text-[11px] text-gray-500">Every claim checked the same way</div>
      </div>
    </div>
  )
}

function ValidateVisual() {
  return (
    <div aria-hidden="true" className="space-y-2.5">
      <div className="rounded-xl bg-white p-3 shadow-lg">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[11px] text-gray-500">DEMO-3107 · Lab</span>
          <StatusPill status="unclean" />
        </div>
        <div className="mt-2 flex items-center justify-between rounded-lg bg-red-50 px-2.5 py-1.5 text-xs ring-1 ring-red-200">
          <span className="font-mono text-red-800">85025 × 3 units</span>
          <span className="text-red-700">MUE limit is 2</span>
        </div>
      </div>
      <div className="flex items-center gap-2 px-1 text-[11px] text-slate-300">
        <Icon name="sparkle" className="h-3.5 w-3.5 text-sky-300" /> Specialist corrects units to 2, then revalidates
      </div>
      <div className="rounded-xl bg-white p-3 shadow-lg">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[11px] text-gray-500">DEMO-3107 · Lab</span>
          <StatusPill status="clean" />
        </div>
        <div className="mt-2 flex items-center justify-between rounded-lg bg-green-50 px-2.5 py-1.5 text-xs ring-1 ring-green-200">
          <span className="font-mono text-green-800">85025 × 2 units</span>
          <span className="text-green-700">Within limit</span>
        </div>
      </div>
    </div>
  )
}

function SendVisual() {
  return (
    <div aria-hidden="true" className="space-y-2.5">
      <div className="rounded-xl bg-white p-3 shadow-lg">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-semibold text-gray-900">Corrected 837</span>
          <span className="rounded-full bg-green-50 px-2 py-0.5 text-[11px] font-semibold text-green-700 ring-1 ring-green-200">
            Ready
          </span>
        </div>
        <div className="mt-1.5 text-[11px] text-gray-500">With a list of every change, for your billing system</div>
      </div>
      <Flow />
      <div className="rounded-xl bg-white/5 p-3 ring-1 ring-white/15">
        <div className="text-xs font-semibold text-white">Your existing submission workflow</div>
        <div className="mt-0.5 text-[11px] text-slate-400">Billing system → clearinghouse → payer</div>
      </div>
      <div className="rounded-xl border border-dashed border-white/20 p-3">
        <div className="flex items-center justify-between gap-2 text-xs text-slate-300">
          Direct clearinghouse connection
          <span className="rounded-full bg-white/10 px-2 py-0.5 text-[11px] text-slate-300">Planned</span>
        </div>
      </div>
    </div>
  )
}

function ThreeSteps() {
  return (
    <section aria-labelledby="steps-title" className="relative overflow-hidden bg-navy py-24 sm:py-28">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(50%_40%_at_50%_0%,rgba(56,189,248,0.12),transparent)]"
      />
      <div className="relative mx-auto max-w-6xl px-5 sm:px-8">
        <SectionHeading id="steps-title" eyebrow="How it works" title="Three Simple Steps. Clearer Claims." inverse>
          From loading a claim to preparing it for submission, VeriClaim keeps the process straightforward.
        </SectionHeading>
        <ol className="mt-14 grid gap-5 lg:grid-cols-3">
          <StepPanel number="01" label="Load" title="Bring Your Claims In." visual={<LoadVisual />}>
            Use API integration, file upload, or manual entry to bring claims into VeriClaim.
          </StepPanel>
          <StepPanel number="02" label="Validate & Correct" title="Find Errors. Fix Them. Move Forward." visual={<ValidateVisual />}>
            VeriClaim checks claims against configured rules and flags issues for billing specialists to review and correct.
          </StepPanel>
          <StepPanel number="03" label="Send" title="Ready for the Next Step." visual={<SendVisual />}>
            Once validated, claims can move forward through the hospital’s established submission workflow.
          </StepPanel>
        </ol>
        <p className="mx-auto mt-10 max-w-2xl text-center text-sm leading-relaxed text-slate-400">
          Validation catches the problems its rules check for: coding pairs, unit limits, coverage policies, prior authorization,
          required fields and payer-specific rules. It can’t catch every possible error, and a clean claim isn’t a guarantee of
          payment.
        </p>
      </div>
    </section>
  )
}

/* --- Problem ---------------------------------------------------------------------- */

function Problem() {
  const items = [
    { title: 'Rejected submissions', text: 'A missing authorization or a mismatched code sends the claim back instead of forward.' },
    { title: 'Repeated corrections', text: 'The same claim is opened, fixed and resubmitted, sometimes more than once.' },
    { title: 'Processing delays', text: 'Every round trip with the payer pushes payment further out.' },
    { title: 'Administrative workload', text: 'Time spent reworking claims is time not spent on the next ones.' },
  ]
  return (
    <section aria-labelledby="problem-title" className="py-24 sm:py-28">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <SectionHeading id="problem-title" eyebrow="Why it matters" title="A Small Claim Error Shouldn’t Create a Big Workflow Problem." />
        <ol className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {items.map((item, index) => (
            <li key={item.title} className="card relative p-6">
              <span className="font-mono text-xs text-gray-400">{String(index + 1).padStart(2, '0')}</span>
              <h3 className="mt-3 text-lg font-semibold text-gray-900">{item.title}</h3>
              <p className="mt-2 text-[15px] leading-relaxed text-gray-600">{item.text}</p>
            </li>
          ))}
        </ol>
        <p className="mt-8 text-center text-[15px] text-gray-600">
          Each of these starts with an error that could have been found before the claim left the building.
        </p>
      </div>
    </section>
  )
}

/* --- Showcase --------------------------------------------------------------------- */

const QUEUE = [
  ['DEMO-2041', 'Medicare', 'Upper GI endoscopy', 'Error', 82],
  ['DEMO-2042', 'Humana MA', 'Brain MRI', 'Error', 71],
  ['DEMO-2048', 'Aetna', 'Hip replacement', 'Warning', 34],
  ['DEMO-2044', 'Blue Cross NC', 'Office visit', 'Pass', 5],
]

const BADGE = {
  Error: 'bg-red-50 text-red-700 ring-red-200',
  Warning: 'bg-amber-50 text-amber-800 ring-amber-200',
  Pass: 'bg-green-50 text-green-700 ring-green-200',
}

function QueueView() {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[32rem] text-left text-sm">
        <thead>
          <tr className="border-b border-gray-100 text-xs text-gray-500">
            <th scope="col" className="py-2 pr-3 font-medium">Claim</th>
            <th scope="col" className="py-2 pr-3 font-medium">Payer</th>
            <th scope="col" className="py-2 pr-3 font-medium">Service</th>
            <th scope="col" className="py-2 pr-3 font-medium">Check</th>
            <th scope="col" className="py-2 text-right font-medium">Risk</th>
          </tr>
        </thead>
        <tbody>
          {QUEUE.map(([id, payer, service, check, risk]) => (
            <tr key={id} className="border-b border-gray-50">
              <td className="py-2.5 pr-3 font-mono text-gray-900">{id}</td>
              <td className="py-2.5 pr-3 text-gray-700">{payer}</td>
              <td className="py-2.5 pr-3 text-gray-700">{service}</td>
              <td className="py-2.5 pr-3">
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${BADGE[check]}`}>{check}</span>
              </td>
              <td className="py-2.5 text-right">
                <span className="inline-flex items-center gap-2">
                  <span className="h-1.5 w-16 overflow-hidden rounded-full bg-gray-100">
                    <span
                      className={`block h-full rounded-full ${risk >= 60 ? 'bg-red-500' : risk >= 30 ? 'bg-amber-500' : 'bg-green-500'}`}
                      style={{ width: `${risk}%` }}
                    />
                  </span>
                  <span className="w-6 text-right tabular-nums text-gray-700">{risk}</span>
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function FixView() {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="rounded-xl bg-red-50/60 p-4 ring-1 ring-red-200">
        <div className="text-xs font-semibold tracking-wide text-red-700 uppercase">Error · NCCI Procedure-to-Procedure Edit</div>
        <p className="mt-1.5 text-sm text-gray-800">CPT 97140 (line 2) is bundled with 97110 on the same day.</p>
        <div className="mt-3 rounded-lg bg-white px-3 py-2 text-xs text-gray-600 ring-1 ring-gray-200">
          <span className="font-semibold text-gray-900">Source:</span> NCCI PTP edit 97110 / 97140, modifier allowed if distinct
        </div>
      </div>
      <div className="rounded-xl bg-white p-4 ring-1 ring-gray-200">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-accent">
          <Icon name="sparkle" className="h-3.5 w-3.5" /> AI Fix suggestion
        </div>
        <p className="mt-1.5 text-sm font-medium text-gray-900">Resolve the NCCI edit on line 2</p>
        <ol className="mt-2 list-decimal space-y-1 pl-4 text-sm text-gray-600">
          <li>Check the documentation for a separate session, site, or practitioner</li>
          <li>If it’s there, add modifier XU or 59; if not, remove the line</li>
        </ol>
        <p className="mt-3 text-xs text-gray-500">Suggestions can be applied and undone. The specialist decides.</p>
      </div>
    </div>
  )
}

function DashboardView() {
  const kpis = [
    ['Clean claim rate', '84.2%'],
    ['Denial rate', '11.8%'],
    ['Claims needing attention', '1,204'],
  ]
  const reasons = [
    ['Missing prior authorization', 92],
    ['Coding: NCCI / MUE', 74],
    ['Diagnosis not covered', 58],
    ['Timely filing', 31],
  ]
  return (
    <div className="grid gap-4 md:grid-cols-[1fr_1.3fr]">
      <div className="grid gap-3">
        {kpis.map(([label, value]) => (
          <div key={label} className="rounded-xl bg-white p-4 ring-1 ring-gray-200">
            <div className="text-xs text-gray-500">{label}</div>
            <div className="mt-1 text-2xl font-semibold tracking-tight tabular-nums text-gray-900">{value}</div>
          </div>
        ))}
      </div>
      <div className="rounded-xl bg-white p-4 ring-1 ring-gray-200">
        <div className="text-xs font-semibold text-gray-900">Top denial reasons</div>
        <ul className="mt-4 space-y-3">
          {reasons.map(([label, value]) => (
            <li key={label}>
              <div className="flex justify-between text-xs text-gray-600">
                <span>{label}</span>
              </div>
              <div className="mt-1 h-2 rounded-full bg-gray-100">
                <div className="h-2 rounded-full bg-accent" style={{ width: `${value}%` }} />
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-[11px] text-gray-400">Illustrative synthetic figures, not results from any hospital.</p>
      </div>
    </div>
  )
}

function AssistantView() {
  return (
    <div className="mx-auto max-w-2xl space-y-3">
      <div className="ml-auto max-w-md rounded-2xl rounded-br-md bg-accent px-4 py-2.5 text-sm text-white">
        Is K21.0 covered for the endoscopy on this claim?
      </div>
      <div className="max-w-xl rounded-2xl rounded-bl-md bg-white px-4 py-3 text-sm leading-relaxed text-gray-800 ring-1 ring-gray-200">
        Yes. The Upper GI Endoscopy policy covers CPT 43239 for K21.0, GERD with esophagitis [S1]. Make sure the documentation
        shows the condition was refractory to PPI therapy, as the policy requires [S1].
        <div className="mt-2.5 flex flex-wrap gap-2 text-xs">
          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-gray-600">[S1] LCD-L33631 · Upper GI Endoscopy</span>
        </div>
      </div>
      <p className="text-center text-xs text-gray-500">
        Answers come from the organisation’s reference tables and cite each record. Only codes and amounts are shared, never
        patient details.
      </p>
    </div>
  )
}

const SHOWCASE = [
  { key: 'queue', label: 'Claims queue', title: 'Riskiest claims first', text: 'Claims with errors rise to the top of the queue, each with its validation result and a 0–100 denial-risk score.', View: QueueView },
  { key: 'fix', label: 'Errors & corrections', title: 'Every error explained', text: 'Each finding names the rule and the reference record behind it, with a suggested correction the specialist can apply or undo.', View: FixView },
  { key: 'dashboard', label: 'Reporting', title: 'See where claims go wrong', text: 'Clean claim rate, denial rate, and the most common reasons, filtered by period, payer and department.', View: DashboardView },
  { key: 'assistant', label: 'Billing assistant', title: 'Answers with sources', text: 'Ask about coverage, coding pairs, prior authorization or appeal wording, and get answers that cite the record they rely on.', View: AssistantView },
]

function Showcase() {
  const [active, setActive] = useState(0)
  const tabs = useRef([])
  const onKey = (event) => {
    const moves = { ArrowRight: 1, ArrowLeft: -1 }
    if (event.key === 'Home' || event.key === 'End' || moves[event.key]) {
      event.preventDefault()
      const next =
        event.key === 'Home' ? 0 : event.key === 'End' ? SHOWCASE.length - 1 : (active + moves[event.key] + SHOWCASE.length) % SHOWCASE.length
      setActive(next)
      tabs.current[next]?.focus()
    }
  }
  const { View, title, text } = SHOWCASE[active]
  return (
    <section aria-labelledby="showcase-title" className="bg-white py-24 sm:py-28">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <SectionHeading id="showcase-title" eyebrow="The product" title="See VeriClaim in Action." />
        <div role="tablist" aria-label="Product views" className="mx-auto mt-10 flex max-w-full gap-1 overflow-x-auto rounded-full bg-gray-100 p-1 sm:w-fit">
          {SHOWCASE.map((tab, index) => (
            <button
              key={tab.key}
              ref={(el) => (tabs.current[index] = el)}
              role="tab"
              type="button"
              id={`tab-${tab.key}`}
              aria-selected={index === active}
              aria-controls={`panel-${tab.key}`}
              tabIndex={index === active ? 0 : -1}
              onKeyDown={onKey}
              onClick={() => setActive(index)}
              className={`shrink-0 rounded-full px-4 py-2 text-sm font-medium transition motion-reduce:transition-none ${
                index === active ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div
          role="tabpanel"
          id={`panel-${SHOWCASE[active].key}`}
          aria-labelledby={`tab-${SHOWCASE[active].key}`}
          tabIndex={0}
          className="mt-8 rounded-[1.75rem] bg-[#f8fafc] p-5 ring-1 ring-gray-200/80 sm:p-8"
        >
          <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
            <div className="max-w-xl">
              <h3 className="text-xl font-semibold text-gray-900">{title}</h3>
              <p className="mt-1 text-[15px] text-gray-600">{text}</p>
            </div>
            <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-semibold tracking-wide text-amber-800 uppercase ring-1 ring-amber-200 ring-inset">
              Synthetic data
            </span>
          </div>
          <div key={SHOWCASE[active].key} className="motion-safe:animate-[site-enter_300ms_ease-out]">
            <View />
          </div>
        </div>
      </div>
    </section>
  )
}

/* --- Features --------------------------------------------------------------------- */

const FEATURES = [
  ['shield', 'Pre-submission validation', 'Every claim is checked before it goes out, and any error or warning blocks submission until it’s resolved.'],
  ['rules', 'Coding checks', 'NCCI procedure pairs, MUE unit limits, LCD/NCD coverage, and whether each line’s diagnosis fits its procedure.'],
  ['check', 'Completeness checks', 'Missing diagnoses, prior authorization numbers, and other required fields are flagged.'],
  ['users', 'Payer-specific rules', 'Rules scoped to a payer, department or claim type, plus each payer’s prior authorization list.'],
  ['claims', 'Clean and unclean classification', 'Each claim is Clean or needs review, with a 0–100 denial-risk score.'],
  ['sparkle', 'Review and correction', 'Suggested fixes with their sources, applied and undone with a full record of what changed.'],
  ['loop', 'API integration', 'Hospital systems send a claim or a file and get back its errors and suggested fixes.'],
  ['plus', 'Manual entry', 'A claim form that fills billing details from the patient’s registration.'],
  ['upload', 'File upload', 'CSV, Excel, or X12 837 files, up to 200 claims at a time.'],
  ['overview', 'Validation reporting', 'Clean claim rate, denial trends and top reasons, by payer and department.'],
  ['book', 'AI-assisted billing support', 'An assistant that answers from the organisation’s reference tables and cites each record.'],
  ['rules', 'Configurable rules', 'Administrators create, test, enable and disable rules without code.'],
]

function Features() {
  return (
    <section aria-labelledby="features-title" className="py-24 sm:py-28">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <SectionHeading id="features-title" eyebrow="Capabilities" title="Powerful Validation. Practical Workflows." />
        <ul className="mt-14 grid gap-px overflow-hidden rounded-[1.5rem] bg-gray-200/80 ring-1 ring-gray-200/80 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(([icon, title, text]) => (
            <li key={title} className="bg-white p-6">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent-soft text-accent">
                <Icon name={icon} className="h-[18px] w-[18px]" />
              </span>
              <h3 className="mt-4 font-semibold text-gray-900">{title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-gray-600">{text}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

/* --- Audiences -------------------------------------------------------------------- */

function Audiences() {
  const people = [
    {
      title: 'Billing Specialists',
      text: 'Identify errors earlier and manage corrections clearly.',
      detail: 'A queue of what needs attention, the reason for each error, and a suggested fix to confirm.',
      motif: (
        <div className="flex items-center justify-between rounded-xl bg-[#f8fafc] p-3 ring-1 ring-gray-200">
          <span className="font-mono text-xs text-gray-600">DEMO-2043</span>
          <StatusPill status="corrected" />
        </div>
      ),
    },
    {
      title: 'Revenue Cycle Leaders',
      text: 'Understand validation outcomes and recurring claim-quality issues.',
      detail: 'Which rules fire most, for which payers and departments, and how that changes over time.',
      motif: (
        <div className="flex h-[52px] items-end gap-1.5 rounded-xl bg-[#f8fafc] p-3 ring-1 ring-gray-200">
          {[40, 65, 50, 80, 55, 35, 28].map((h, i) => (
            <span key={i} className="flex-1 rounded-sm bg-accent/70" style={{ height: `${h}%` }} />
          ))}
        </div>
      ),
    },
    {
      title: 'Hospital Finance Teams',
      text: 'Explore opportunities to reduce avoidable billing rework.',
      detail: 'Claims at risk, days in AR and net collection, set against the problems found before submission.',
      motif: (
        <div className="flex items-center justify-between rounded-xl bg-[#f8fafc] p-3 ring-1 ring-gray-200">
          <span className="text-xs text-gray-600">Claims at risk</span>
          <span className="text-sm font-semibold tabular-nums text-gray-900">Before submission</span>
        </div>
      ),
    },
  ]
  return (
    <section aria-labelledby="audiences-title" className="bg-white py-24 sm:py-28">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <SectionHeading id="audiences-title" eyebrow="Built for hospital teams" title="Designed Around the People Behind Every Claim." />
        <ul className="mt-14 grid gap-5 lg:grid-cols-3">
          {people.map((p) => (
            <li key={p.title} className="flex flex-col rounded-[1.5rem] bg-[#f8fafc] p-6 ring-1 ring-gray-200/80">
              <div aria-hidden="true">{p.motif}</div>
              <h3 className="mt-6 text-xl font-semibold text-gray-900">{p.title}</h3>
              <p className="mt-2 text-[15px] font-medium text-gray-800">{p.text}</p>
              <p className="mt-2 text-sm leading-relaxed text-gray-600">{p.detail}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

/* --- Status ----------------------------------------------------------------------- */

const STATUS = [
  ['Working application', 'Completed', 'done'],
  ['Synthetic-data demonstration', 'Available', 'done'],
  ['Hospital pilot recruitment', 'Current', 'current'],
  ['Live hospital pilot evaluation', 'Planned', 'planned'],
  ['Wider availability', 'Future', 'planned'],
]

function Status() {
  return (
    <section aria-labelledby="status-title" className="py-24 sm:py-28">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <SectionHeading id="status-title" eyebrow="Where we are" title="Built. Demonstrated. Preparing for Hospital Pilots." />
        <ol className="mt-14 grid gap-4 md:grid-cols-5">
          {STATUS.map(([title, label, state], index) => (
            <li key={title} className="relative">
              <div className="flex items-center gap-3 md:flex-col md:items-start">
                <span
                  aria-hidden="true"
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                    state === 'done'
                      ? 'bg-green-600 text-white'
                      : state === 'current'
                        ? 'bg-accent text-white ring-4 ring-accent/20'
                        : 'bg-white text-gray-500 ring-1 ring-gray-300'
                  }`}
                >
                  {state === 'done' ? <Icon name="check" className="h-4 w-4" /> : index + 1}
                </span>
                {index < STATUS.length - 1 && (
                  <span aria-hidden="true" className="absolute top-4 left-10 hidden h-px w-[calc(100%-2.5rem)] bg-gray-300 md:block" />
                )}
                <div>
                  <div
                    className={`text-xs font-semibold tracking-wide uppercase ${
                      state === 'done' ? 'text-green-700' : state === 'current' ? 'text-accent' : 'text-gray-500'
                    }`}
                  >
                    {label}
                  </div>
                  <div className="mt-0.5 font-medium text-gray-900">{title}</div>
                </div>
              </div>
            </li>
          ))}
        </ol>
        <div className="mt-14 flex flex-col items-center justify-between gap-4 rounded-[1.5rem] bg-white p-6 ring-1 ring-gray-200/80 sm:flex-row sm:p-8">
          <div>
            <h3 className="text-xl font-semibold text-gray-900">Interested in Becoming a Pilot Partner?</h3>
            <p className="mt-1 text-[15px] text-gray-600">We’re looking for a small number of hospitals to evaluate VeriClaim with us.</p>
          </div>
          <Link href="/pilot" className="btn-primary shrink-0 px-6 py-3 text-base">
            Request a Pilot
          </Link>
        </div>
      </div>
    </section>
  )
}

/* --- Final call to action --------------------------------------------------------- */

export function ClosingCta() {
  return (
    <section aria-labelledby="closing-title" className="relative overflow-hidden bg-navy py-24 sm:py-28">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(45%_60%_at_50%_100%,rgba(10,108,224,0.35),transparent)]"
      />
      <div className="relative mx-auto max-w-3xl px-5 text-center sm:px-8">
        <h2 id="closing-title" className="text-3xl font-semibold tracking-tight text-balance text-white sm:text-5xl sm:leading-[1.08]">
          Better Claims Start with Cleaner Submissions.
        </h2>
        <p className="mx-auto mt-5 max-w-xl text-lg leading-relaxed text-slate-300">
          Discover how VeriClaim could fit your billing workflow and help your team identify errors earlier.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link href="/#demo" className="btn bg-white px-6 py-3 text-base text-gray-900 hover:bg-gray-100">
            Explore the Demo
          </Link>
          <Link href="/pilot" className="btn-primary px-6 py-3 text-base">
            Request a Pilot
          </Link>
        </div>
      </div>
    </section>
  )
}

export default function Home() {
  return (
    <>
      <Hero />
      <ThreeSteps />
      <Problem />
      <Showcase />
      <Features />
      <Audiences />
      <Status />
      <ClosingCta />
    </>
  )
}
