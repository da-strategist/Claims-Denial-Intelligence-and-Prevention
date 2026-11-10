import { useEffect, useRef, useState } from 'react'
import Icon from '../components/Icon'
import { CHECKS, DEMO_CLAIMS, totalCharge } from './demoClaims'
import { prefersReducedMotion } from './router'

const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

const STEP_INDEX = { loaded: 0, validating: 1, flagged: 1, corrected: 1, clean: 1, send: 2 }
const STEPS = ['Load', 'Validate & Correct', 'Send']

const CHECK_MS = 260

/** Clean, Review required, or not yet validated: the app's own colours (green good, red errors). */
export function StatusPill({ status }) {
  const styles = {
    pending: ['bg-gray-100 text-gray-600 ring-gray-200', 'Not validated'],
    validating: ['bg-accent-soft text-accent ring-accent/20', 'Validating…'],
    unclean: ['bg-red-50 text-red-700 ring-red-200', 'Unclean · Review required'],
    corrected: ['bg-amber-50 text-amber-800 ring-amber-200', 'Corrected · Revalidate'],
    clean: ['bg-green-50 text-green-700 ring-green-200', 'Clean · Passed validation'],
  }
  const [classes, label] = styles[status]
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${classes}`}>
      {status === 'clean' && <Icon name="check" className="h-3.5 w-3.5" />}
      {status === 'unclean' && <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-red-500" />}
      {label}
    </span>
  )
}

function Stepper({ current }) {
  return (
    <ol className="flex items-center gap-2 text-xs font-medium sm:gap-3 sm:text-sm" aria-label="Workflow">
      {STEPS.map((label, index) => {
        const done = index < current
        const active = index === current
        return (
          <li key={label} className="flex items-center gap-2 sm:gap-3" aria-current={active ? 'step' : undefined}>
            <span
              className={`flex items-center gap-2 rounded-full px-2.5 py-1 transition-colors motion-reduce:transition-none ${
                active ? 'bg-accent text-white' : done ? 'bg-green-50 text-green-700' : 'text-gray-500'
              }`}
            >
              <span
                aria-hidden="true"
                className={`flex h-5 w-5 items-center justify-center rounded-full text-[11px] ${
                  active ? 'bg-white/20' : done ? 'bg-green-600 text-white' : 'bg-gray-200 text-gray-600'
                }`}
              >
                {done ? <Icon name="check" className="h-3 w-3" /> : index + 1}
              </span>
              {label}
              {done && <span className="sr-only"> (done)</span>}
            </span>
            {index < STEPS.length - 1 && <span aria-hidden="true" className="h-px w-3 bg-gray-300 sm:w-6" />}
          </li>
        )
      })}
    </ol>
  )
}

/** Highlight for the field at issue: red while flagged, green once corrected. */
function mark(issue, stage, where) {
  if (!issue) return ''
  const { field } = issue
  const match = where.header ? field.header === where.header : field.line === where.line && field.column === where.column
  if (!match) return ''
  if (stage === 'flagged') return 'bg-red-50 ring-2 ring-red-400 text-red-800 motion-safe:animate-[pulse_1.6s_ease-in-out_2]'
  if (stage === 'corrected' || stage === 'clean' || stage === 'send') return 'bg-green-50 ring-2 ring-green-400 text-green-800'
  return ''
}

function ClaimCard({ claim, issue, stage, status }) {
  const cell = 'rounded-md px-1.5 py-0.5 transition-colors duration-500 motion-reduce:transition-none'
  return (
    <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-200/80 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-mono text-xs text-gray-500">{claim.id}</div>
          <div className="text-base font-semibold text-gray-900">{claim.summary}</div>
        </div>
        <StatusPill status={status} />
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-xs text-gray-500">Patient</dt>
          <dd className="text-gray-900">{claim.patient}</dd>
        </div>
        <div>
          <dt className="text-xs text-gray-500">Payer</dt>
          <dd className="text-gray-900">{claim.payer}</dd>
        </div>
        <div>
          <dt className="text-xs text-gray-500">Service date</dt>
          <dd className="text-gray-900">{claim.serviceDate}</dd>
        </div>
        <div>
          <dt className="text-xs text-gray-500">Prior authorization</dt>
          <dd className={`-mx-1.5 inline-block ${cell} ${mark(issue, stage, { header: 'priorAuth' })}`}>{claim.priorAuth}</dd>
        </div>
      </dl>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[30rem] text-left text-sm">
          <caption className="sr-only">Service lines</caption>
          <thead>
            <tr className="border-b border-gray-100 text-xs text-gray-500">
              <th scope="col" className="py-1.5 pr-2 font-medium">Line</th>
              <th scope="col" className="py-1.5 pr-2 font-medium">CPT</th>
              <th scope="col" className="py-1.5 pr-2 font-medium">Modifier</th>
              <th scope="col" className="py-1.5 pr-2 font-medium">Procedure</th>
              <th scope="col" className="py-1.5 pr-2 font-medium">Diagnosis</th>
              <th scope="col" className="py-1.5 pr-2 text-right font-medium">Units</th>
              <th scope="col" className="py-1.5 text-right font-medium">Charge</th>
            </tr>
          </thead>
          <tbody>
            {claim.lines.map((l, index) => (
              <tr key={l.cpt} className="border-b border-gray-50 last:border-0">
                <td className="py-2 pr-2 text-gray-500">{index + 1}</td>
                <td className="py-2 pr-2 font-mono text-gray-900">{l.cpt}</td>
                <td className="py-2 pr-2 font-mono">
                  <span className={`-mx-1.5 ${cell} ${mark(issue, stage, { line: index, column: 'modifier' })}`}>
                    {l.modifier || '—'}
                  </span>
                </td>
                <td className="py-2 pr-2 text-gray-700">{l.description}</td>
                <td className="py-2 pr-2 font-mono">
                  <span className={`-mx-1.5 ${cell} ${mark(issue, stage, { line: index, column: 'dx' })}`}>{l.dx}</span>
                </td>
                <td className="py-2 pr-2 text-right tabular-nums text-gray-700">{l.units}</td>
                <td className="py-2 text-right tabular-nums text-gray-700">{currency.format(l.units * l.charge)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex justify-end text-sm text-gray-500">
        Total <span className="ml-2 font-semibold tabular-nums text-gray-900">{currency.format(totalCharge(claim))}</span>
      </div>
    </div>
  )
}

function CheckList({ progress, failed }) {
  return (
    <ul className="grid gap-1.5 text-sm sm:grid-cols-2" aria-label="Validation checks">
      {CHECKS.map((check, index) => {
        const done = index < progress
        const flagged = done && check.key === failed
        return (
          <li key={check.key} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] transition-colors motion-reduce:transition-none ${
                flagged ? 'bg-red-600 text-white' : done ? 'bg-green-600 text-white' : 'bg-gray-200 text-gray-400'
              }`}
            >
              {flagged ? '!' : done ? <Icon name="check" className="h-3 w-3" /> : ''}
            </span>
            <span className={done ? 'text-gray-900' : 'text-gray-500'}>{check.label}</span>
            <span className="sr-only">{flagged ? ': issue found' : done ? ': passed' : ': waiting'}</span>
          </li>
        )
      })}
    </ul>
  )
}

/**
 * The website's interactive demonstration of Load → Validate & Correct → Send, on synthetic
 * claims, entirely in the browser: nothing is sent anywhere. Every stage is a click away, so
 * it never plays on its own; with reduced motion the checks complete at once.
 */
export default function ClaimDemo() {
  const [selected, setSelected] = useState(DEMO_CLAIMS[0].id)
  const original = DEMO_CLAIMS.find((c) => c.id === selected)
  const [claim, setClaim] = useState(original)
  const [stage, setStage] = useState('loaded') // loaded, validating, flagged, corrected, clean, send
  const [progress, setProgress] = useState(0)
  const [round, setRound] = useState(1) // 2 once a corrected claim is revalidated
  const [exported, setExported] = useState(false)
  const timer = useRef(null)

  useEffect(() => () => clearInterval(timer.current), [])

  const issue = original.issue
  const failedCheck = round === 1 ? issue?.check : null

  const load = (id) => {
    clearInterval(timer.current)
    setSelected(id)
    setClaim(DEMO_CLAIMS.find((c) => c.id === id))
    setStage('loaded')
    setProgress(0)
    setRound(1)
    setExported(false)
  }

  const validate = (nextRound) => {
    setRound(nextRound)
    setStage('validating')
    const failing = nextRound === 1 ? issue?.check : null
    const stopAt = failing ? CHECKS.findIndex((c) => c.key === failing) + 1 : CHECKS.length
    const finish = () => setStage(failing ? 'flagged' : 'clean')
    if (prefersReducedMotion()) {
      setProgress(CHECKS.length)
      finish()
      return
    }
    setProgress(0)
    let done = 0
    timer.current = setInterval(() => {
      done += 1
      setProgress(done)
      if (done >= stopAt) {
        clearInterval(timer.current)
        // A failing check still lets the rest finish, as the engine runs every rule
        setProgress(CHECKS.length)
        finish()
      }
    }, CHECK_MS)
  }

  const correct = () => {
    setClaim(issue.apply(claim))
    setStage('corrected')
  }

  const status = {
    loaded: 'pending',
    validating: 'validating',
    flagged: 'unclean',
    corrected: 'corrected',
    clean: 'clean',
    send: 'clean',
  }[stage]

  const announcement = {
    loaded: `Claim ${claim.id} loaded. Not validated yet.`,
    validating: 'Validating the claim.',
    flagged: issue ? `Review required: ${issue.rule}.` : '',
    corrected: issue ? `${issue.applied}. Revalidate to confirm.` : '',
    clean: 'Clean: the claim passed validation.',
    send: 'Ready for submission.',
  }[stage]

  return (
    <div className="overflow-hidden rounded-[1.75rem] bg-white/70 shadow-[0_30px_80px_-30px_rgba(11,23,48,0.35)] ring-1 ring-gray-200/80 backdrop-blur">
      {/* Window bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200/70 bg-white px-4 py-3 sm:px-5">
        <Stepper current={STEP_INDEX[stage]} />
        <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-semibold tracking-wide text-amber-800 uppercase ring-1 ring-amber-200 ring-inset">
          Demonstration · synthetic data
        </span>
      </div>

      <div className="grid gap-0 lg:grid-cols-[15rem_1fr]">
        {/* Sample claims */}
        <div className="border-b border-gray-200/70 bg-gray-50/80 p-3 lg:border-r lg:border-b-0">
          <div className="eyebrow px-2 pb-2">Sample claims</div>
          <ul className="flex gap-2 overflow-x-auto lg:flex-col lg:overflow-visible" aria-label="Sample claims">
            {DEMO_CLAIMS.map((c) => {
              const active = c.id === selected
              return (
                <li key={c.id} className="shrink-0">
                  <button
                    type="button"
                    onClick={() => load(c.id)}
                    aria-pressed={active}
                    className={`w-full rounded-xl px-3 py-2.5 text-left transition motion-reduce:transition-none ${
                      active ? 'bg-white shadow-sm ring-1 ring-gray-200' : 'hover:bg-white/70'
                    }`}
                  >
                    <div className="font-mono text-[11px] text-gray-500">{c.id}</div>
                    <div className="text-sm font-medium whitespace-nowrap text-gray-900">{c.summary}</div>
                    <div className="text-xs text-gray-500">{c.payer}</div>
                  </button>
                </li>
              )
            })}
          </ul>
        </div>

        {/* Workspace */}
        <div className="space-y-4 p-4 sm:p-6">
          <p className="sr-only" role="status" aria-live="polite">
            {announcement}
          </p>
          <div key={claim.id} className="motion-safe:animate-[site-enter_400ms_ease-out]">
            <ClaimCard claim={claim} issue={issue} stage={stage} status={status} />
          </div>

          {stage === 'loaded' && (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-gray-600">Claim loaded. Run it through the configured rules.</p>
              <button type="button" className="btn-primary px-5 py-2.5" onClick={() => validate(1)}>
                Validate claim
              </button>
            </div>
          )}

          {(stage === 'validating' || stage === 'flagged' || stage === 'clean') && (
            <div className="rounded-2xl bg-white p-4 ring-1 ring-gray-200/80">
              <div className="eyebrow pb-3">{round === 2 ? 'Revalidation' : 'Validation'}</div>
              <CheckList progress={progress} failed={failedCheck} />
            </div>
          )}

          {stage === 'flagged' && (
            <div className="rounded-2xl bg-red-50/60 p-4 ring-1 ring-red-200 motion-safe:animate-[site-enter_300ms_ease-out] sm:p-5">
              <div className="text-xs font-semibold tracking-wide text-red-700 uppercase">Error · {issue.rule}</div>
              <p className="mt-1.5 text-sm leading-relaxed text-gray-800">{issue.explanation}</p>
              <div className="mt-4 rounded-xl bg-white p-3.5 ring-1 ring-gray-200">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-accent">
                  <Icon name="sparkle" className="h-3.5 w-3.5" /> Suggested correction
                </div>
                <p className="mt-1 text-sm text-gray-700">{issue.fix}</p>
                <p className="mt-1 text-xs text-gray-500">The billing specialist confirms it against the documentation before applying.</p>
              </div>
              <div className="mt-4 flex justify-end">
                <button type="button" className="btn-primary px-5 py-2.5" onClick={correct}>
                  {issue.action}
                </button>
              </div>
            </div>
          )}

          {stage === 'corrected' && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-green-50/60 p-4 ring-1 ring-green-200">
              <p className="flex items-center gap-2 text-sm text-gray-800">
                <Icon name="check" className="h-4 w-4 text-green-700" />
                {issue.applied}.
              </p>
              <button type="button" className="btn-primary px-5 py-2.5" onClick={() => validate(2)}>
                Revalidate
              </button>
            </div>
          )}

          {stage === 'clean' && (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-gray-600">Every configured check passed.</p>
              <button type="button" className="btn-primary px-5 py-2.5" onClick={() => setStage('send')}>
                Continue to Send <Icon name="arrow" className="h-4 w-4" />
              </button>
            </div>
          )}

          {stage === 'send' && (
            <div className="space-y-3 motion-safe:animate-[site-enter_400ms_ease-out]">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl bg-white p-4 ring-2 ring-accent/40">
                  <div className="text-sm font-semibold text-gray-900">Hand off to your billing system</div>
                  <p className="mt-1 text-sm text-gray-600">
                    Export the corrected 837 and a list of what changed, then submit through your existing workflow.
                  </p>
                  {exported ? (
                    <p className="mt-3 flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2 font-mono text-xs text-green-800" role="status">
                      <Icon name="check" className="h-3.5 w-3.5" /> {claim.id}-corrected.837 prepared (demo: nothing is sent)
                    </p>
                  ) : (
                    <button type="button" className="btn-primary mt-3" onClick={() => setExported(true)}>
                      Export corrected 837
                    </button>
                  )}
                </div>
                <div className="rounded-2xl bg-gray-50 p-4 ring-1 ring-gray-200">
                  <div className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                    Send through a clearinghouse
                    <span className="rounded-full bg-gray-200 px-2 py-0.5 text-[11px] font-semibold text-gray-600">Planned</span>
                  </div>
                  <p className="mt-1 text-sm text-gray-600">
                    A direct clearinghouse connection is planned after the pilot. VeriClaim doesn’t transmit claims to payers today.
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-gray-500">
                  Clean means the claim passed the configured checks. It doesn’t guarantee the payer will accept or pay it.
                </p>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => load(DEMO_CLAIMS[(DEMO_CLAIMS.findIndex((c) => c.id === selected) + 1) % DEMO_CLAIMS.length].id)}
                >
                  Try another claim
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
