import { useAuth } from '../hooks/useAuth'
import PageHeader, { Page } from '../components/PageHeader'
import { ClaimStatusBadge, ValidationBadge } from '../components/StatusBadge'

const ROLE_LABELS = { analyst: 'Analyst', biller: 'Biller', admin: 'Administrator' }

const ROLE_SUMMARY = {
  analyst: 'You can read claims and the overview. Patient names and details are hidden for your role.',
  biller: 'You can enter, fix, and submit claims, and see patient details.',
  admin: 'You can do everything a biller can, and also manage rules and read the audit log.',
}

function Steps({ children }) {
  return <ol className="list-decimal space-y-1.5 pl-5 text-[15px] text-gray-700 marker:text-gray-400">{children}</ol>
}

function Tip({ children }) {
  return <p className="rounded-xl bg-gray-50 px-4 py-3 text-sm text-gray-600">{children}</p>
}

function Term({ name, children }) {
  return (
    <div className="grid gap-1 py-2.5 sm:grid-cols-[9rem_1fr] sm:gap-4">
      <dt className="text-sm">{name}</dt>
      <dd className="text-sm text-gray-600">{children}</dd>
    </div>
  )
}

/** Sections in reading order; `permission` limits a section to roles that can use it. */
const SECTIONS = [
  {
    id: 'start',
    title: 'Getting started',
    body: ({ user }) => (
      <>
        <p className="text-[15px] text-gray-700">
          Your administrator creates your account. Sign in with your username and password. After{' '}
          {user.idle_timeout_minutes} minutes without activity you’re signed out, and anything not
          yet saved is lost, so save a draft before you step away. Five wrong passwords in a row
          lock the account for 15 minutes.
        </p>
        <p className="text-[15px] text-gray-700">
          You’re signed in as <strong className="font-medium">{ROLE_LABELS[user.role] ?? user.role}</strong>.{' '}
          {ROLE_SUMMARY[user.role]} This guide only shows what your role can do.
        </p>
      </>
    ),
  },
  {
    id: 'overview',
    title: 'Overview',
    body: () => (
      <>
        <p className="text-[15px] text-gray-700">
          The first number is the one to act on: how many claims need attention because they have
          validation errors. <strong className="font-medium">Review claims</strong> opens exactly
          those claims, for the same period, payer, and department you’ve chosen.
        </p>
        <p className="text-[15px] text-gray-700">
          Below it are the key measures compared with the previous period (green is better, red is
          worse), then revenue, why claims are denied, AR aging, and payers.
        </p>
      </>
    ),
  },
  {
    id: 'queue',
    title: 'Fixing claims that need attention',
    body: ({ canEdit }) => (
      <>
        <Steps>
          <li>
            Open <strong className="font-medium">Claims</strong>. It starts on{' '}
            <strong className="font-medium">Needs attention</strong>, riskiest first. Switch to{' '}
            <strong className="font-medium">All claims</strong> to see everything submitted.
          </li>
          <li>Click a claim to open it. The left side lists each problem with a suggested fix.</li>
          {canEdit ? (
            <>
              <li>
                Where it says <strong className="font-medium">Fix available</strong>, check or fill in
                the values and choose <strong className="font-medium">Apply fix &amp; re-validate</strong>.
                The claim is checked again straight away.
              </li>
              <li>
                Changed your mind? <strong className="font-medium">Undo corrections</strong> restores
                the claim’s original values. Every fix records who applied it.
              </li>
            </>
          ) : (
            <li>Fixes are shown so you can see what’s wrong; applying them needs a biller.</li>
          )}
          <li>
            For judgement calls (medical necessity, modifiers, prior auth, appeal wording), choose{' '}
            <strong className="font-medium">Ask the assistant</strong>. Its answer cites the
            reference records it used.
          </li>
        </Steps>
        <Tip>
          The assistant never receives patient names, IDs, or dates; it gets codes and amounts
          only, and names typed into a question are masked. The panel shows exactly what was sent.
        </Tip>
      </>
    ),
  },
  {
    id: 'new-claim',
    title: 'Entering a new claim',
    permission: 'claims:write',
    body: () => (
      <>
        <Steps>
          <li>
            Open <strong className="font-medium">New Claim</strong> and find a registered patient by
            name or ID. Their primary payer, date of birth, address, and member ID are filled in
            from their registration; check them, especially when marked as sample details.
          </li>
          <li>
            Add the provider, dates, diagnoses (primary first), and a service line for each
            diagnosis. Leave a charge blank to use the procedure’s standard charge.
          </li>
          <li>
            Not finished? Choose <strong className="font-medium">Save draft</strong> at any point.
            Nothing is checked yet.
          </li>
          <li>
            When it’s complete, choose <strong className="font-medium">Create &amp; validate claim</strong>.
            It’s checked against the rules and opens right there with any problems and fixes.
          </li>
          <li>
            Once nothing is flagged, choose <strong className="font-medium">Mark as submitted</strong>.
            The claim becomes Pending and moves to Claims, and its 837 claim file is created; use{' '}
            <strong className="font-medium">Download 837</strong> on the claim to get it, or the{' '}
            <strong className="font-medium">CMS-1500/UB-04 PDF</strong> and{' '}
            <strong className="font-medium">Readable 837 PDF</strong> to read or print it. A file
            marked <strong className="font-medium">Test file</strong> can’t go to a payer until an
            administrator completes the EDI settings.
          </li>
        </Steps>
      </>
    ),
  },
  {
    id: 'drafts',
    title: 'Drafts: picking up unfinished work',
    permission: 'claims:write',
    body: () => (
      <>
        <p className="text-[15px] text-gray-700">
          The <strong className="font-medium">Drafts</strong> panel on the right of New Claim is
          shared by every biller, so anyone can finish a claim someone else started. Click a row to
          open it.
        </p>
        <dl className="divide-y divide-gray-100">
          <Term name="Saved forms">
            Unfinished forms from Save draft. Not checked against the rules. Deleted 30 days after
            the last save.
          </Term>
          <Term name="Draft claims">
            Created and checked, but not submitted. The dot shows what’s left to resolve.
          </Term>
        </dl>
      </>
    ),
  },
  {
    id: 'submit',
    title: 'Why won’t my claim submit?',
    permission: 'claims:write',
    body: () => (
      <>
        <p className="text-[15px] text-gray-700">
          A claim can’t be submitted while it has any <strong className="font-medium">error</strong>{' '}
          or <strong className="font-medium">warning</strong>; this applies to claims entered here
          and through the API. The rules are checked again as you submit, using today’s date,
          so a draft left too long can pick up a Timely Filing warning.
        </p>
        <Steps>
          <li>Open the claim and work through each problem listed.</li>
          <li>Apply the suggested fix, or correct the claim and re-validate.</li>
          <li>
            If a warning can’t be fixed on the claim (for example a genuinely high-value claim), ask
            an administrator to review the rule.
          </li>
        </Steps>
      </>
    ),
  },
  {
    id: 'colours',
    title: 'What the labels mean',
    body: () => (
      <dl className="divide-y divide-gray-100">
        <Term name={<ValidationBadge status="pass" />}>No rule flagged the claim.</Term>
        <Term name={<ValidationBadge status="warning" />}>Needs review; blocks submission until resolved.</Term>
        <Term name={<ValidationBadge status="error" />}>Will likely be denied; blocks submission.</Term>
        <Term name={<ValidationBadge status="aifix" />}>An error on a high-risk claim (60+); a fix is suggested.</Term>
        <Term name="Risk score">0–100 likelihood of denial. Under 30 is low (green), 30–59 medium (amber), 60+ high (red).</Term>
        <Term name={<ClaimStatusBadge status="Draft" />}>Created, not yet submitted.</Term>
        <Term name={<ClaimStatusBadge status="Pending" />}>Submitted, waiting for the payer.</Term>
        <Term name={<ClaimStatusBadge status="Pending" overdue />}>Waiting longer than this payer usually takes to pay.</Term>
        <Term name={<ClaimStatusBadge status="Paid" />}>Paid by the payer.</Term>
        <Term name={<ClaimStatusBadge status="Denied" />}>Refused by the payer; the claim shows why and how to appeal.</Term>
      </dl>
    ),
  },
  {
    id: 'admin',
    title: 'For administrators',
    permission: 'audit:read',
    body: () => (
      <>
        <dl className="divide-y divide-gray-100">
          <Term name="Rules">
            Create, edit, switch off, or test rules. Changes apply to every claim immediately;
            switching off a rule also stops it blocking submission.
          </Term>
          <Term name="Audit Log">
            Every request: who, what, which records, and the outcome. Filter by user, record, or
            outcome; the hash check shows whether the log has been altered.
          </Term>
          <Term name="Accounts">
            Created and managed on the server with <code className="font-mono text-xs">python -m app.users</code>{' '}
            (add, password, role, disable).
          </Term>
        </dl>
      </>
    ),
  },
]

/** How to use the tool, showing only what the signed-in role can do. */
export default function UserGuide() {
  const { user } = useAuth()
  const can = (permission) => !permission || user.permissions.includes(permission)
  const sections = SECTIONS.filter((section) => can(section.permission))
  const context = { user, canEdit: can('claims:write') }

  return (
    <Page>
      <PageHeader title="User guide" subtitle="How to get claims right the first time." />
      <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-[13rem_minmax(0,1fr)]">
        <nav aria-label="Guide contents" className="lg:sticky lg:top-6">
          <ol className="flex flex-wrap gap-1 lg:flex-col">
            {sections.map((section) => (
              <li key={section.id}>
                <a
                  href="#/guide"
                  onClick={(event) => {
                    // Hash routing owns the URL, so scroll instead of following an anchor
                    event.preventDefault()
                    document.getElementById(`guide-${section.id}`)?.scrollIntoView({ behavior: 'smooth' })
                  }}
                  className="block rounded-lg px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-200/50 hover:text-gray-900"
                >
                  {section.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>
        <div className="space-y-6">
          {sections.map((section) => (
            <section
              key={section.id}
              id={`guide-${section.id}`}
              aria-labelledby={`guide-${section.id}-title`}
              className="card scroll-mt-6 space-y-4 p-6 sm:p-8"
            >
              <h2 id={`guide-${section.id}-title`} className="text-xl font-semibold tracking-tight text-gray-900">
                {section.title}
              </h2>
              <section.body {...context} />
            </section>
          ))}
        </div>
      </div>
    </Page>
  )
}
