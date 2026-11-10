# VeriClaim — Claim Validation Tool

Pre-submission claim validation and denial prevention for hospital revenue cycle teams.
Every claim is checked against configurable rules and scored for denial risk; flagged claims
get rule-based fix suggestions, and an executive dashboard tracks the results. Built with a
FastAPI backend and a React frontend over a synthetic 120,000-claim data set.

## What it does

| Page | Purpose |
|---|---|
| **Overview** | Opens on the number of submitted claims that need attention (the same claims the Claims queue shows), with a button straight to them, and for billers a line for draft claims still to finish on New Claim. Then KPIs (denial rate, clean claim rate, days in AR, net collection, at-risk claims) against the prior period, revenue trend, validation status, top denial reasons, AR aging, payer performance. Filter by period, payer, department. |
| **Claims** | Opens on the **Needs attention** queue: claims with validation errors (Error or AI Fix), riskiest first. **All claims** shows every submitted claim (drafts are finished on New Claim). Search and filter; each row shows its validation result and 0–100 risk score. Expand a claim for findings, risk breakdown, lines, denials, and **AI Fix** suggestions that can be applied and undone. Suggestions that need judgement (medical necessity, NCCI/modifiers, payer prior auth, appeals) offer **Ask the assistant**. A submitted claim shows its 837 with downloads (the file, a CMS-1500/UB-04 PDF, a readable PDF). Colours carry meaning: green for Paid, Pass and low risk; amber for warnings and medium risk; red for errors, denials and high risk. |
| **New Claim** | Enter a draft claim for a registered patient: selecting them fills in their primary payer, date of birth, address and member ID from their registration; billed payer plus secondary/tertiary coverage, each with its policy, up to 12 diagnoses each supported by a service line, prior authorization. A **Drafts** panel on the right lists everything waiting to be finished, shared by every biller: **saved forms** (from **Save draft**: unfinished, not validated, deleted 30 days after the last save) and **draft claims** (created and validated, not yet submitted). Opening a draft claim shows its problems, AI fixes, and **Mark as submitted**, which is only allowed once no rule error or warning remains. The same check applies to claims sent through the API. |
| **Rules** | Create, edit, enable/disable, and test rules (field + operator + value conditions, AND/OR, scoped to payers, departments, or claim types). Changes apply to every claim immediately. |
| **JAB Audit** | Conceptual integration with the JAB Audit underpayment recovery platform: workflow, architecture, and the proposed API contracts. |
| **User Guide** | Short task-by-task help for billers, analysts, and administrators. Each person sees only the sections their role can use. |

### Clarification assistant

Answers a billing specialist's questions from the organization's reference tables, citing
each record it relies on as [S1], [S2]:

| Use case | Sources |
|---|---|
| Medical necessity | LCD/NCD coverage policies (`ref_lcd_ncd_policies`) |
| NCCI / modifiers | NCCI PTP edits, MUE limits (`ref_ncci_ptp_edits`, `ref_mue_limits`) |
| Payer prior auth and terms | Payer profiles and contracts (`dim_payers`, `dim_payer_contracts`) |
| Appeal wording | CARC/RARC codes (`ref_carc_codes`, `ref_rarc_codes`), plus the above |
| Expected payment | Medicare fee schedule (`ref_physician_fee_schedule`) |

Retrieval is deterministic: the claim's CPT, ICD-10, payer, and CARC/RARC codes look up the
records that govern them (e.g. an NCCI edit when both of its codes are billed, an MUE when units
exceed the limit, a coverage policy noting whether the diagnosis is on its covered list), and
keyword search handles free-typed questions. Claude then writes the answer from those records
only. Without `ANTHROPIC_API_KEY` the assistant returns the matching records instead.

**Shared with Claude:** codes and amounts only (CPT, ICD-10, modifiers, units, payer, claim
type, place of service, charges, prior auth status, CARC/RARC, service year). Never patient
or provider names, IDs, age, gender, ZIP, NPI, PA numbers, any date finer than the year, or
denial free text. In the question, IDs, dates, and the names of registered patients and
providers are masked. The panel shows exactly what was shared.

### Sign-in, roles, and the audit log

Every route except `/api/health` needs a signed-in user, and each role gets only what it needs:

| Role | Can |
|---|---|
| `analyst` | View claims, validation, suggestions, dashboard, assistant. No patient names or demographics. |
| `biller` | Also see patient details and search patients, enter and submit claims, apply and undo fixes |
| `admin` | Also create and edit validation rules, manage user accounts, and read the audit log |

Sessions are an HttpOnly, SameSite=Strict cookie. They end after 15 minutes without a request,
after 8 hours, at sign-out, or when the account is disabled; the API restarting also ends
them. Passwords are salted scrypt hashes, at least 12 characters with mixed case and a digit
or symbol, and five wrong attempts lock the account for 15 minutes.

Every API request is appended to `backend/logs/audit.jsonl` with the user, the action, the
records involved, search parameters, and the outcome (success, denied, failed). Each event
holds the hash of the one before it, so an edited or deleted line is detected; the Audit Log
page (admins) shows events and checks the chain. Questions to the assistant aren't logged,
only the claim they concern. Applied corrections also record who applied them.

### Claim lifecycle

```
Draft ──(Mark as submitted)──▶ Pending ──▶ Paid / Denied
                                  └─ Overdue: pending longer than the payer's average days to pay
```

Submission is blocked while a claim has any rule error or warning, whether it was entered on screen or through the API. Draft claims are finished on the New Claim page, not listed under Claims, and aren't counted in denial rate or AR. Until it's submitted, a claim entered in the app can be corrected with **Edit claim** (or `PUT /claims/{id}`): it keeps its ID and patient, the rules run again, its AI Fix corrections are folded in, and the audit log names the fields that changed. Submitted claims can't be edited.

### 837 claim files

Every claim carries what an X12 837 needs, from the New Claim form or the API's `billing`
object: the patient's date of birth and address, each payer's policy (member ID, group,
and the policy holder when it isn't the patient), and for institutional claims the type of
bill, admission type and source, patient status, and a revenue code per line. Selecting a
patient fills these from their registration: what their last claim captured, or, for the
synthetic sample patients, generated sample details (marked as such). Creating a claim
saves its details back to the patient's registration.

**Mark as submitted** creates the 837P (professional) or 837I (institutional) and saves it
with the claim as the record of what was sent; billers and admins can download it, and each
download is audited. Self-pay claims are billed to the patient, so they get no 837.

Two PDFs are built from that saved file, so they always match what was sent: the claim on a
**CMS-1500** (837P) or **UB-04** (837I) layout with the official box numbers (a reference
copy for reading and printing, not the red-ink OCR form payers scan), and a **readable 837**
that names each part of the file, shows where every value sits, and ends with the raw file.
Test files carry a "TEST FILE" mark on every page.

Administrators keep the organisation's identifiers under **Claim file settings** on the Users
page (`GET/PUT /organisation/edi-settings`, saved as `edi_settings.json` in its folder, audited by
field name). Files going back to a hospital's own billing system need no clearinghouse, and name
the hospital as receiver unless one is set. A facility whose address on file has a 5-digit ZIP
can be given its ZIP+4 there. The identifiers: submitter,
clearinghouse (receiver), billing provider (name, NPI, 9-digit EIN, address with ZIP+4), and
each payer's electronic payer ID. Until every one is set, `mode` is `production`, and the
facility address has a ZIP+4, files are marked as test files (ISA15 = T) and the claim lists
what's missing. See `app/services/edi_settings.py` for the file's shape.

### Coding checks on service lines

Four seed rules check a claim's lines against the organisation's reference tables, the same
ones the assistant cites. Diagnoses are judged per line, by the diagnosis each line points to,
as payers do:

| Rule | Flags a claim when |
|---|---|
| NCCI Procedure-to-Procedure Edit | Two of its procedures form an NCCI edit (`ref_ncci_ptp_edits`) in effect on the service date. Where the edit allows a modifier, 59 or XE/XS/XP/XU on either line bypasses it; otherwise nothing does |
| Units Exceed MUE Limit | A procedure's units, added up across lines, exceed its MUE (`ref_mue_limits`) |
| Diagnosis Not Covered (LCD/NCD) | A procedure has a coverage policy (`ref_lcd_ncd_policies`) and the diagnosis its line points to isn't on the covered list (error) |
| Diagnosis Doesn't Match Procedure | A specialty procedure without a policy (cardiology, behavioural, neurology, OB/GYN, oncology, orthopaedics, pulmonology, rehab, surgery) points to a diagnosis from an unrelated ICD-10 chapter, e.g. an echocardiogram for diabetes. Symptom (R) and encounter (Z) codes always fit; office visits, labs, imaging and preventive care aren't screened. A rough screen by chapter, not a payer crosswalk, so it's a warning (`PLAUSIBLE_CHAPTERS` in `coding_edits.py`) |

The first three are errors. A real diagnosis-to-procedure crosswalk (payers' LCD article ICD-10
lists, or a commercial one) would make the fourth precise; there's none in the reference data yet.

They test four rule fields (`ncci_conflict`, `mue_exceeded`, `diagnosis_not_covered`,
`diagnosis_procedure_mismatch`), so
administrators can disable them, change their severity, or combine them with other conditions.
AI Fix names the line and the reference record, and points a line at a fitting diagnosis already
on the claim when there is one. A corrected primary diagnosis clears a coverage error at once;
line problems are fixed by editing the draft. The checks run on claims entered, uploaded or
sent through the API, the ones that haven't gone out yet. The source data's adjudicated claims
aren't checked, because their synthetic lines would flag about two thirds of them. Organisations
whose rules were saved before these rules existed get them added once (`seed_version` in
`rules.json`); a rule an administrator deletes later stays deleted.

### Payer documents behind the rules

Administrators upload a payer's own documents on the Rules page: a provider manual, policy
or prior authorization list, as PDF or text (up to 15 MB), with its payer and effective date.
The text of each page is read on upload (a text file is read in parts of about 3,000
characters); a scanned PDF with no text is kept but can't be searched.

- **Rules cite them.** A rule's **Source** names a document, a page and the passage it's based
  on. Claims the rule flags show that source with a link to the document, and AI Fix lists it
  among its citations. A document a rule cites can't be deleted (409) until no rule cites it.
- **The assistant searches them.** Each page is a source keyed by its payer and the codes it
  mentions. Only the claim's own payer's documents (or a payer named in the question) are
  used, and the question's wording or a billed code picks the page; answers name the
  document and page. Page text is sent to Claude like the other reference sources; it holds
  no patient details.
- **Kept per organisation.** `payer_documents.json` and the `payer_documents/` folder, encrypted
  with the organisation's key (contract terms can be confidential) and included in its data
  export. Uploads, downloads and deletions are in the audit log by document ID.

Drafting rules from a document is Stage 2 in `PHASES.md`.

### Risk score (0–100)

25 points per rule error, 10 per warning, 20 for prior patient denials (+5 if preventable),
5–15 for AR aging past 30/60/90 days, 15 for missing prior auth, 10 for a missing diagnosis.
Capped at 100. A fact is only counted once: missing prior auth or a missing diagnosis adds no extra
points when a rule already flags it. A non-clean claim counts once, through the Non-Clean Claim Review rule (a
warning), not again as a risk factor. New claims start clean. A claim with an error and a score of 60+ is routed to AI Fix.

## Setup

Prerequisites: Python 3.12+ with [uv](https://docs.astral.sh/uv/), Node.js 20.19+ or 22.12+, and the
synthetic data in `../Data/raw_data/`.

```bash
# Backend — from the repository root (Healthcare_RCM_Project/)
uv sync
cd claim_validation_tool/backend
uv run python -m app.orgs migrate        # creates the first organisation, "meridian", over Data/raw_data
uv run python -m app.orgs add-sample     # optional: the synthetic "lakeside" practice, for demos
# optional: one state of CMS's synthetic Medicare inpatient claims (data.cms.gov), as "cms-florida"
uv run python -m app.orgs add-cms --claims inpatient.csv --beneficiaries beneficiary_2025.csv \
  --icd-descriptions icd10cm_codes_2025.txt --hcpcs-descriptions HCPC2025_JAN_ANWEB_12172024.txt
uv run python -m app.users add yourname --name "Your Name" --role admin --org meridian   # prompts for a password
uv run uvicorn app.main:app --reload --port 8000
```

### Organisations

Several organisations can use one installation, each completely walled off from the others
(see `DATA_SEGREGATION_PLAN.md`). Each has its own folder under `backend/orgs/` (git-ignored,
readable only by the account running the API) holding its rules, corrections, saved drafts,
new claims and their 837s, patient registrations, 837 settings, and audit log, plus its own
claims CSVs. Every account belongs to one organisation, and every request reaches only that
organisation's data: another organisation's records are "not found". The sidebar shows the
organisation's name. `uv run python -m app.orgs list` shows organisations; `add` registers a
new one over its CSVs. `migrate` moves a single-organisation install into "meridian" and is
safe to run twice. An automated test tries every API route with another organisation's IDs.

**Need-to-know access.** By default everyone sees their whole organisation. An administrator
can limit a person, on the Users page (**Change** under their name), to some departments,
facilities, and/or providers; they then see a claim if it matches any of those. The limit
applies everywhere: claim lists and the queue, claim details, fixes, the assistant, 837 and
PDF downloads, the Overview's figures, saved forms and draft claims, and which providers they
can pick for a new claim. They can still find any registered patient to start a claim, but
only see that patient's claims and history inside their access. A limited person sees
"Showing only: …" on Overview, Claims, and New Claim. Administrators are always
organisation-wide. Changes apply on the person's next action.

**Platform administration.** Whoever runs the hosted service uses a *platform* account
(`uv run python -m app.users add ops --name "Ops" --role platform`, no `--org`). It belongs to
no organisation and sees no patient data. Its **Platform** page lists organisations (status,
accounts, active admins), creates new ones together with their first administrator (both or
neither; the organisation starts with the shared code sets and empty tables for its own
data), adds further administrators, and suspends or
reactivates organisations (suspending signs their users out at once). It records each
organisation's business associate agreement (BAA); a missing one is flagged, and in
production mode (`RCM_ENVIRONMENT=production`) blocks the organisation's sign-ins. A
suspended organisation can be deleted for good, by typing its ID: its encryption key is
destroyed first, then its data and accounts; a record of it stays so its ID isn't reused.
Organisations' administrators can't create platform accounts.

**Encryption at rest.** With `RCM_MASTER_KEY` set, each organisation's files holding patient
data (new claims, drafts, corrections, registrations, its audit log, and claims tables in
its own folder) are encrypted with its own key, which the master key protects. Create the
key and encrypt an existing install with the API stopped:

```bash
uv run python -m app.orgs new-master-key    # add to backend/.env as RCM_MASTER_KEY=…, and back it up separately
uv run python -m app.orgs encrypt           # safe to run twice
uv run python -m app.orgs rotate-key        # after putting a new key first in RCM_MASTER_KEY, or choosing a new RCM_KEY_PROVIDER
uv run python -m app.orgs key-status        # which key provider holds each organisation's key
```

The hash check also catches the newest events being removed, using `logs/audit-head.json`
(back it up with the rest of `logs/`, and restore them together). Restoring an older copy of
both, or changes by someone holding the key, needs a copy kept outside the server to catch.

The audit log keeps each closed year in its own file (`logs/audit-2026.jsonl`) and every
event for at least `RCM_AUDIT_RETENTION_YEARS` (6). Years past that can be deleted, never
automatically, with the API running or not:

```bash
uv run python -m app.orgs audit-purge --dry-run   # what would go
uv run python -m app.orgs audit-purge --by "Ana Diaz"  # delete it; recorded in the log, and the hash check still covers what's left
```

Without the master key the data can't be read, so keep a copy somewhere separate (a
password manager or key vault). Production mode refuses to start without one. Details in
`DATA_SEGREGATION_PLAN.md` §9.

**Data export.** An organisation's administrators download all its data, decrypted, as one
zip with a manifest (Audit log page, **Export all data**). The download is in its audit log.

**Emergency (break-glass) access.** To look inside an organisation, e.g. for a support case,
a platform account starts emergency access with a written reason (20+ characters) for 15
minutes to 4 hours. It is **read-only** (claims and patients), shown in a red banner on every
page, and ends at the set time or earlier, by the platform or by the organisation's
administrators. Starting it, ending it, and every request made with it are in the
organisation's own audit log, and its administrators see each grant and its reason on their
Audit Log page. Grants are kept in `backend/orgs/break_glass.json`.

### How claims leave

VeriClaim works alongside a hospital's billing system. A draft can be **handed off**
(`POST /api/claims/{id}/hand-off`: the billing system sends it, open issues must be
acknowledged) or **submitted** (`POST /api/claims/{id}/submit`: blocked by any rule error or
warning). A claim takes one route; `POST /api/claims/{id}/reopen` puts a handed-off claim
back to Draft once someone confirms it wasn't sent. Administrators choose which route is
offered first on the Users page (default: the hospital's billing system).

Once handed off, the claim can go back to the billing system: `GET /api/claims/{id}/handoff`
summarises it, `…/handoff/837` downloads its 837 with the corrections in, and
`…/handoff/changes.pdf` lists what changed since it was first entered or uploaded (net of
AI Fix and edits: a value changed back isn't listed) and what was still open. Only billers and
admins can export, each download is audited (field names, never values), and every download
of a claim keeps one control number until it's reopened. The file is a first-time claim
(frequency code 1) because nothing has reached a payer, and CLM01 carries the hospital's own
number when the claim was uploaded with one. It's marked as a test file until the EDI settings
are complete. Self-pay claims get the list only.

### What a clean claim doesn't cover

**Prior authorization.** An 837 carries an authorization number only when someone got one, so a
claim can't show that it needed one. Administrators keep each payer's list of services needing
prior authorization on the Users page (`prior_auth_lists.json`; no patient details). A claim for a listed
service is marked as requiring it however it arrived, and the claim can't override that; the existing
rule then flags it if there's no authorization. `prior_auth_check` reports `obtained`, `missing`,
`not_needed` (a list exists and no service is on it), `not_assessed` (no list, or saved before it) or
`not_applicable` (self-pay). `obtained` means the claim carries an authorization, not that the payer
confirmed it. Only the primary payer's list and CPT/HCPCS codes are used, so inpatient
admission authorizations without such a code aren't caught. Saved claims don't change when a list does.

**Coverage.** `coverage_check` is always `not_checked` (`not_applicable` for self-pay). Confirming
active coverage needs a 270/271 eligibility check with the payer, which isn't built.

### Claims API for hospital systems

Administrators create a key on the Users page. Send it as `Authorization: Bearer <key>`. A key
works on `/api/v1` only, and sign-in cookies don't work there. Nothing sent here goes to a payer.

```bash
# An 837P/837I, or a CSV/Excel file in the upload template's layout (up to 200 claims, 5 MB)
curl -X POST "$API/api/v1/claims/file" -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d "{\"filename\": \"claims.837\", \"content\": \"$(base64 < claims.837)\"}"
```

Each checked claim comes back with `claim_id`, `claim_number`, `status`, `clean`, `open_issues`,
`coverage_check`, `prior_auth_check`, `findings` and `suggestions`, and never patient details beyond `patient_id`. `POST /api/v1/claims`
takes one claim as JSON: `claim_number`, this organisation's payer and provider IDs, and either
`patient` (name and sex; the date of birth, address and member ID are in `billing`) or `patient_id`.

**The patient list keeps itself up to date.** The hospital's register is the master; ours is a working
copy (`patient_list.json`, encrypted, laid over `dim_patients`, which is never modified) holding only
name, age, sex, ZIP code and primary payer, with date of birth, address and policies in the
registrations file. A patient on a claim is never refused for being new, through the API or file
upload: a clear match (same name and date of birth, or name and member ID) updates them, no match
adds them, and an unclear match (same name with another date of birth, same member ID with this payer, or the same
date of birth with the same first or last name) adds them with `patient_needs_review`. Those appear
on the Claims page for staff; nothing is merged automatically, and merging isn't built yet. A patient is
only listed if their claim saved. The list says what claims have told us, not whether coverage is active.
Providers and payers still have to be set up: a claim naming an unknown one is refused.

The hospital's claim number identifies the claim: send it again and the Draft is replaced and
rechecked, so a corrected claim or a retry never makes a second one. Once the system sends the claim
itself, `POST /api/v1/claims/{claim_id}/handoff` finishes it here (open issues need
`{"acknowledge_open_issues": true}`); after that the number can't be replaced (409). Too many
requests get 429 with `Retry-After`. Every request is in the audit log as `api.<key id>`, without
the claim number, which can be a patient account number.

### Pilot requests

The website's **Request a pilot** form (`POST /api/pilot-requests`, no sign-in) saves the
request and opens the visitor's email app with a copy addressed to `VITE_PILOT_CONTACT_EMAIL`.
Platform accounts see requests on the **Platform** page: **Approve** creates the organisation and
its first administrator from the request (with a temporary password), **Decline** keeps a reason.
Requests are encrypted with the platform's own data key in `<RCM_ORGS_DIR>/_platform/`, deleted
12 months after a decision, and audited in the platform audit log. The form is limited per email
and network address, and has a hidden honeypot field.

### Accounts

The first administrator is created on the command line, as above. After that, administrators
manage accounts on the **Users** page (Admin section): add people, change roles, reset
passwords, and disable or re-enable accounts. Disabling or resetting a password signs that
person out. A password an administrator sets for someone else (a new account or a reset) is
temporary: after signing in with it, they must choose their own before anything else opens.
Anyone can change their own password from the account menu (`POST /api/auth/password`, which
ends their other sessions). Administrators can't change their own role or disable themselves, and the last
active administrator can't be demoted or disabled. Every change is audited (never the
password). Administrators only see and manage their own organisation's accounts; usernames
are unique across all organisations. The same is possible with `uv run python -m app.users`
(`list`, `add … --org`, `password`, `role`, `disable`, `enable`); changes apply while the API
runs. Accounts live in `backend/users.json` (git-ignored, readable only by you).

To have Claude answer the clarification assistant's questions, put the key in
`backend/.env` (git-ignored) as `ANTHROPIC_API_KEY=...` and start the API with
`uv run --env-file .env uvicorn app.main:app --reload --port 8000`.

API docs: http://localhost:8000/docs. Loading the data takes a few seconds at startup.

```bash
# Frontend — in a second terminal
cd claim_validation_tool/frontend
npm install
npm run dev
```

Website: http://localhost:5173 · App: http://localhost:5173/app. The Vite dev server proxies `/api` to port 8000.

### Website and app

One build serves both. The public website is at `/` (Home with the interactive Load →
Validate & Correct → Send demo over synthetic claims), `/about`, `/pilot` (pilot interest),
`/sign-up` (says access is by invitation), `/privacy` and `/terms`. The claims app, with its
sign-in and hash routes, is at `/app`; older bookmarks such as `/#/claims` are sent to
`/app#/claims`, and `/sign-in` and `/login` open the app. Each half is loaded only when
it's visited.

Content only the owner can supply (team profiles, founder story, mission and vision
approval, legal pages) lives in `frontend/src/site/content.js`; until it's filled in, the
pages show labelled placeholders. The pilot form saves the request for the Platform page
(see Pilot requests) and opens the visitor's email app addressed to `VITE_PILOT_CONTACT_EMAIL`;
without that address, the form says requests aren't open yet.

### HTTPS

On this computer, Caddy serves the app at **https://localhost:8443**, in front of the API
(:8000) and the dev server (:5173), with a certificate from mkcert:

```bash
brew install mkcert caddy
mkcert -install                      # once: trust mkcert's local certificate authority (asks for your Mac password)
./deploy/https-local.sh              # with the API and `npm run dev` running
```

On a server, `deploy/Caddyfile.production` gets and renews a Let's Encrypt certificate
for your domain by itself, serves the built frontend (`npm run build`), adds HSTS and a
strict content security policy, and passes `/api/*` to the API listening on 127.0.0.1
only. Run the API there with `RCM_ENVIRONMENT=production`, `RCM_COOKIE_SECURE=1`, and
`RCM_ALLOWED_ORIGINS=https://<your domain>`; instructions are at the top of the file.
The pilot server on AWS (one EC2 instance with KMS, set up by script) is in
`deploy/aws/README.md`; the demo stays on Fly and Vercel.
`http://localhost:5173` keeps working during development (Chrome treats localhost as
secure, so the HTTPS-only cookie is still sent).

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `RCM_ORGS_DIR` | `backend/orgs` | Organisations: `organisations.json` and one folder per organisation with its `rules.json` (seeded with 9 defaults), `claim_corrections.json`, `claim_drafts.json` (expire 30 days after the last save), `new_claims.json` (with their 837s), `patient_registrations.json`, `claim_changes.json` (edits to claims, for the list of changes), `edi_settings.json`, and `logs/audit.jsonl` |
| `ANTHROPIC_API_KEY` | unset | Enables Claude for the clarification assistant |
| `RCM_ASSISTANT_MODEL` | `claude-sonnet-5-5` | Claude model the assistant uses |
| `RCM_ASSISTANT_MODE` | | Set to `retrieval` to keep Claude off even with a key |
| `RCM_USERS_FILE` | `backend/users.json` | Sign-in accounts (API keys are kept beside it in `api_keys.json`, digests only) |
| `RCM_API_RATE_PER_MINUTE` | `120` | Requests each API key may make per minute |
| `RCM_AUDIT_FILE` | `backend/logs/audit.jsonl` | Platform audit log: requests that belong to no organisation (e.g. sign-in with an unknown username). Each organisation's own log is in its folder |
| `RCM_AUDIT_RETENTION_YEARS` | `6` | Years audit events are kept before `audit-purge` may delete them; less than 6 is refused |
| `RCM_SESSION_IDLE_MINUTES` | `15` | Sign out after this long without a request |
| `RCM_SESSION_MAX_HOURS` | `8` | Longest a session lasts |
| `RCM_SESSIONS_FILE` | unset | Keep sign-in sessions in this file so a restart doesn't sign everyone out (digests only). For a demo host that stops and starts on its own; refused in production |
| `RCM_COOKIE_SECURE` | off | Set to `1` behind HTTPS so the session cookie is never sent over plain HTTP |
| `RCM_MASTER_KEY` | unset | Turns on encryption at rest: wraps each organisation's data key (`orgs/<id>/data_key.enc`). To replace it: put the new key first, comma, then the old; run `python -m app.orgs rotate-key`; then remove the old |
| `RCM_KEY_PROVIDER` | `local` | Where the master key lives: `local` uses `RCM_MASTER_KEY`; `aws-kms` uses AWS KMS (`RCM_KMS_KEY_ID`). Azure Key Vault and Google Cloud KMS are planned; see `DATA_SEGREGATION_PLAN.md` §9.6 |
| `RCM_KMS_KEY_ID` | unset | With `aws-kms`: the KMS key's ARN, ID or alias. Credentials and `AWS_REGION` come the usual AWS way (on EC2, the instance role, needing `kms:Encrypt`, `kms:Decrypt` and `kms:DescribeKey` on that key) |
| `RCM_CODE_SETS_DIR` | unset | The shared code sets new organisations start from (`python -m app.orgs code-sets <dir>` writes them, with no patients or claims). Required in production; elsewhere an existing organisation's code sets are used |
| `RCM_ENVIRONMENT` | unset | `production` refuses to start without a master key (`RCM_MASTER_KEY` or a key service) or `RCM_COOKIE_SECURE=1`, or while any sample organisation exists; blocks sign-in for organisations without a BAA on record; and drops the sign-in page's "synthetic data" line |
| `RCM_PUBLIC_URL` | unset | The site's public address (e.g. `https://rcm.example.com`), for the single sign-on callback behind a proxy; sign-in returns to `/app` there |
| `RCM_ALLOWED_ORIGINS` | `http://localhost:5173` | Web addresses the app is served from (comma-separated), for the browser's cross-origin check |
| `VITE_API_BASE` | `/api` | API base URL for the frontend |
| `VITE_PILOT_CONTACT_EMAIL` | unset | Address the website's pilot form emails (set at build time, e.g. in Vercel). Unset: the form is disabled |

Each organisation's app data persists in its folder (git-ignored, readable only by the account
running the API). The source CSVs are never modified: new claims and their submission dates are
replayed on startup.

## Testing

```bash
cd claim_validation_tool/backend && uv run python -m pytest   # API, engine, risk, AI fix, workflow
cd claim_validation_tool/frontend && npm test                 # components, pages, hooks, API client
npm run lint                                                  # oxlint
npm run build                                                 # production build
```

Assistant evaluation, 17 billing questions with expected sources and answer facts
(`backend/app/evals/assistant_cases.py`):

```bash
cd claim_validation_tool/backend
uv run python -m app.evals.assistant          # retrieval recall and MRR (free, offline)
uv run --env-file .env python -m app.evals.assistant --llm   # also grades Claude's answers
```

Backend tests run against small fixture CSVs in `backend/app/tests/fixtures/`, never the real
data; `test_workflow.py` walks one claim from patient search to overdue. Frontend tests use
Vitest and Testing Library with `fetch` stubbed (`src/test/mockApi.js`).

## API

All routes are under `/api`; full schemas at `/docs`.

| Area | Endpoints |
|---|---|
| Pilot requests | `POST /pilot-requests` (public form) · `GET /platform/pilot-requests` · `POST /platform/pilot-requests/{id}/approve` · `POST /platform/pilot-requests/{id}/decline` (platform accounts) |
| Sign-in | `POST /auth/login` · `POST /auth/logout` · `GET /auth/me` · `POST /auth/password` (your own) · `GET /auth/sso/{org}/start` · `GET /auth/sso/{org}/callback` (single sign-on) |
| Audit | `GET /audit` (username, record_id, outcome, limit) · `GET /audit/verify` |
| Users | `GET /users` · `POST /users` · `PATCH /users/{username}` · `POST /users/{username}/password` (administrators) |
| Platform | `GET/POST /platform/organisations` · `POST /platform/organisations/{id}/suspend` · `…/reactivate` · `…/admins` · `…/baa` · `PUT/DELETE …/sso` · `…/delete` · `…/emergency-access` · `GET /platform/emergency-access` · `POST /platform/emergency-access/{id}/end` · `GET /platform/audit` (platform accounts) |
| Organisation | `GET /organisation/export` (administrators: zip of all its data) · `PUT /organisation/settings` · `GET/PUT /organisation/edi-settings` · `GET/POST /organisation/api-keys` · `DELETE /organisation/api-keys/{id}` |
| Claims API for hospital systems (API key only) | `POST /v1/claims` · `POST /v1/claims/file` · `GET /v1/claims/{id}` · `POST /v1/claims/{id}/handoff` |
| Emergency access (organisation side) | `GET /audit/emergency-access` · `POST /audit/emergency-access/{id}/end` (administrators) |
| Claims | `GET /claims` (search, filter, sort, page) · `POST /claims` · `POST /claims/import` (CSV/Excel or 837 file → Draft claims) · `GET /claims/import/template.csv` · `GET /claims/{id}` · `PUT /claims/{id}` (edit a Draft) · `POST /claims/{id}/submit` · `GET /claims/{id}/837` · `GET /claims/{id}/claim-form.pdf` · `GET /claims/{id}/837-readable.pdf` · `GET /claims/{id}/handoff` · `GET /claims/{id}/handoff/837` · `GET /claims/{id}/handoff/changes.pdf` |
| Saved drafts | `GET /drafts` · `POST /drafts` · `GET /drafts/{id}` · `PUT /drafts/{id}` · `DELETE /drafts/{id}` (billers and admins) |
| Validation | `GET /validate/{id}` · `POST /validate` (up to 200 claims) |
| Rules | `GET/POST /rules` · `GET/PUT/PATCH/DELETE /rules/{id}` · `GET /rules/fields` · `POST /rules/test` |
| Payer documents | `GET/POST /payer-documents` · `GET/DELETE /payer-documents/{id}` · `GET /payer-documents/{id}/file` · `GET /payer-documents/{id}/pages/{page}` |
| AI Fix | `GET /aifix/{id}` · `POST /aifix/{id}/apply` · `DELETE /aifix/{id}/corrections` |
| Dashboard | `GET /dashboard` (months, payer_id, department_id) |
| Reference | `/patients`, `/patients/{id}`, `/patients/{id}/registration`, `/payers`, `/departments`, `/providers`, `/facilities`, `/codes/procedures`, `/codes/diagnoses` |
| Assistant | `POST /assistant` (question, optional claim_id and topic) · `GET /assistant/status` |
| JAB Audit | `GET /jab/contracts` |
| Health | `GET /health` |

Errors return `{"detail": ...}`: a message for 401 (signed out), 403 (role lacks the
permission), 404/409/422 business errors, or FastAPI's field list for request validation errors.

## Project structure

```
claim_validation_tool/
├── PROJECT_GUIDE.md        # Architecture, conventions, domain context
├── PHASES.md               # Build phases and progress
├── deploy/                  # Caddy configs for HTTPS: local (mkcert) and production (Let's Encrypt)
├── backend/app/
│   ├── main.py             # FastAPI app, CORS, audit middleware, routers, data preload
│   ├── users.py            # Account management CLI (python -m app.users)
│   ├── orgs.py             # Organisations CLI: list, add, migrate, add-sample, add-cms
│   ├── cms_org.py          # Builds an organisation from CMS synthetic inpatient claims
│   ├── sample_org.py       # Generates the synthetic Lakeside Family Practice
│   ├── routers/            # One module per API area
│   ├── models/             # Pydantic request/response schemas
│   ├── services/           # Validation engine, risk scorer, AI fix, assistant, dashboard, JAB,
│   │                       #   837 builder/reader/settings, claim PDFs
│   ├── data/               # Claims repository, rule/correction/user/draft/new-claim/registration
│   │                       #   stores, audit log, knowledge base
│   ├── evals/              # Assistant evaluation set and runner
│   └── tests/              # pytest suite and fixture CSVs
└── frontend/src/
    ├── Root.jsx            # Website at /, claims app at /app
    ├── App.jsx             # App shell and hash routes
    ├── site/               # Public website: pages, layout, claim demo, owner content
    ├── pages/              # Login, Dashboard, ClaimsWorkbench, NewClaim, RuleManager, JabAudit, AuditLog, Users, UserGuide
    ├── components/         # Shared UI (badges, panels, builders, error boundary)
    ├── hooks/              # Data hooks built on useApi
    ├── services/api.js     # The only place that calls fetch
    ├── utils/              # Formatting, routes, rule summaries, claim entry helpers
    └── test/               # Vitest setup and fetch mock
```

## Limitations

- Synthetic data: payer, coding (LCD/NCCI/MUE), and contract checks are limited to what it contains.
  Some defaults suit only this sample (the Overview opens on All time, sample patient details are
  generated); `PHASES.md` lists what to change before going live on real claims.
- Not yet fit for real patient data: HTTPS is tested only on this computer (the server
  config is ready but there's no server yet), the encryption master key sits in `.env` rather
  than a key service, local accounts rather than single sign-on, and no agreement (BAA/DPA)
  with Anthropic. Sessions live in memory, so a
  restart signs everyone out.
- AI Fix is rule-based; the assistant handles the ambiguous cases. Its knowledge is limited to
  the reference tables and the payer documents an organisation uploads: without a payer's
  manual it can't say which services that payer requires prior authorization for, or quote
  filing limits, and says so.
