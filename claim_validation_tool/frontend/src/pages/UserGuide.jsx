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
          {ROLE_SUMMARY[user.role]} This guide only shows what your role can do. The sidebar shows
          your organisation; you only ever see its patients and claims. If an administrator has
          limited you to some departments, facilities, or providers, the main pages say “Showing
          only: …”.
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
          those claims, for the same period, payer, and department you’ve chosen. Draft claims
          aren’t in that number; if any are waiting, a line underneath says how many, with{' '}
          <strong className="font-medium">Open drafts</strong> to finish them on New Claim.
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
            Spotted a mistake, like a missing prior authorization? Choose{' '}
            <strong className="font-medium">Edit claim</strong> at the top of the claim. The form
            reopens with everything filled in; <strong className="font-medium">Save changes &amp; validate</strong>{' '}
            keeps the same claim number and checks it again. The patient can’t change, and a claim
            can’t be edited once it’s submitted.
          </li>
          <li>
            If you send claims from your own billing system, choose{' '}
            <strong className="font-medium">Hand off to billing system</strong>. Nothing goes to the
            payer from here. If issues are still open you can tick the box to fix them over there;
            they stay listed on the claim. The claim then offers its 837 file to import and a{' '}
            <strong className="font-medium">List of changes</strong> PDF, showing each value as it was
            and as it is now. An uploaded claim keeps your claim number (claim_ref, or the number in
            your 837) in the file, and the file is a first-time claim, not a replacement. To change it
            or send it from here instead, choose{' '}
            <strong className="font-medium">Reopen claim</strong> and confirm your system hasn’t sent it.
          </li>
          <li>
            To send from VeriClaim, once nothing is flagged, choose{' '}
            <strong className="font-medium">Mark as submitted</strong>.
            The claim becomes Pending and moves to Claims, and its 837 claim file is created; use{' '}
            <strong className="font-medium">Download 837</strong> on the claim to get it, or the{' '}
            <strong className="font-medium">CMS-1500/UB-04 PDF</strong> and{' '}
            <strong className="font-medium">Readable 837 PDF</strong> to read or print it. A file
            marked <strong className="font-medium">Test file</strong> can’t go to a payer until an
            administrator completes the claim file settings on the Users page.
          </li>
        </Steps>
      </>
    ),
  },
  {
    id: 'upload-claims',
    title: 'Uploading claims from a file',
    permission: 'claims:write',
    body: () => (
      <>
        <Steps>
          <li>
            On <strong className="font-medium">New Claim</strong>, choose{' '}
            <strong className="font-medium">Upload claims</strong>. Use a CSV or Excel file in the
            template’s layout (<strong className="font-medium">Download CSV template</strong>), or an
            837P or 837I file from another billing system.
          </li>
          <li>
            In the template, each row is a service line and rows with the same claim_ref make one
            claim. List the claim’s diagnoses in one cell, primary first, separated by |. Billing
            details left blank (date of birth, address, member ID) come from the patient’s
            registration.
          </li>
          <li>
            837 files are matched to your patient list by name and date of birth, to providers by NPI,
            and to payers by ID or name. A patient who isn’t on the list yet is added from the
            claim, so they’re never refused for being new. If they might be someone already listed,
            both records are kept and they appear under{' '}
            <strong className="font-medium">patients to check</strong> on the Claims page. A claim
            with an unknown provider or payer is listed with the reason.
          </li>
          <li>
            Choose <strong className="font-medium">Upload and check</strong>. Each claim is saved as
            a draft claim and checked against the rules, exactly as if it had been typed in. Claims
            that couldn’t be read are listed with what to fix; the rest are saved. Nothing is
            submitted.
          </li>
          <li>
            Open a claim from the results or the Drafts panel to fix what’s flagged, then submit it
            as usual.
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
            Created and checked, but not submitted. The dot shows what’s left to resolve. Open one
            and choose Edit claim to correct it.
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
          A claim can’t be submitted from VeriClaim while it has any <strong className="font-medium">error</strong>{' '}
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
        <Term name={<ClaimStatusBadge status="Handed off" />}>Finished here; your billing system sends it. A handed-off claim can’t also be submitted from here.</Term>
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
          <Term name="Payer documents">
            On the Rules page, upload a payer’s manual, policy or prior authorization list (PDF or text).
            In a rule, under Source, choose the document, the page, and the passage the rule is based on:
            claims it flags then show that source, and so does AI Fix. The assistant also searches the
            documents and names the page it used. A document a rule cites can’t be deleted until the rule
            stops citing it.
          </Term>
          <Term name="Audit Log">
            Every request: who, what, which records, and the outcome. If the service’s operators
            ever need emergency access to your data, it appears at the top with their reason, and
            you can end it at any time; it is read-only and everything they open is logged. Filter by user, record, or
            outcome; the hash check shows whether the log has been altered. Events are kept for at
            least six years; if older years have been deleted under that policy, the page says
            which.
          </Term>
          <Term name="Users">
            Add people, change their role, reset a password, or disable an account (which signs
            them out). Under each person, <strong className="font-medium">Change</strong> limits what
            they see to some departments, facilities, or providers (everyone sees the whole
            organisation until you do). You can’t change your own role or disable yourself, and the last active
            administrator can’t be removed. Every change is in the audit log. Give new passwords
            in person or by phone, not by email. The same can be done on the server with{' '}
            <code className="font-mono text-xs">python -m app.users</code>.
          </Term>
          <Term name="API keys">
            On the Users page: a key lets your billing or hospital system send claims and read back
            errors and suggested fixes, without anyone signing in. Claims it sends appear here as
            Drafts, and sending the same claim number again replaces the Draft. A key reaches only
            that, can act across your whole organisation, and appears in the audit log as{' '}
            <code className="font-mono text-xs">api.</code> plus its ID. It’s shown once; if one is
            lost or leaked, revoke it and create another.
          </Term>
          <Term name="Prior authorization lists">
            On the Users page: the services each payer requires prior authorization for, from your own
            payer lists. A claim for a listed service with no authorization on it is flagged, however it
            arrived. It checks the claim carries an authorization, not that the payer has confirmed it.
            Claims for a payer with no list show prior auth as not assessed.
          </Term>
          <Term name="Coverage active?">
            Not checked. A claim with no errors can still be denied because the patient’s coverage had
            ended, so confirm coverage with the payer as you do today.
          </Term>
          <Term name="Export all data">
            On the Audit Log page: one zip with everything your organisation has here (claims,
            drafts, corrections, patient details, the audit log, your accounts without passwords),
            decrypted, with a manifest to check it’s complete. It holds patient data: store and
            send it only as your HIPAA policies allow. Each download is in the audit log.
          </Term>
        </dl>
      </>
    ),
  },
  {
    id: 'platform',
    title: 'For the platform',
    permission: 'platform:manage',
    body: () => (
      <dl className="divide-y divide-gray-100">
        <Term name="Organisations">
          Create an organisation, add its first administrator, and suspend or reactivate it.
          You see names and account counts, never patients or claims.
        </Term>
        <Term name="BAA">
          Record each organisation’s signed business associate agreement before it loads real
          patient data. Without one, its people can’t sign in once the service runs in production.
        </Term>
        <Term name="Emergency access">
          Read-only, time-limited, with a reason the organisation sees in its audit log.
        </Term>
        <Term name="Delete">
          Only a suspended organisation, by typing its ID. Its encryption key is destroyed, then
          its data and accounts. It can’t be undone, so its administrators should export their
          data first.
        </Term>
      </dl>
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
