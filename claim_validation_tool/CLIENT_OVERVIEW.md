# ClaustraRCM: How It Works

*A plain-language overview for hospital revenue cycle, IT and compliance leads.*
*Status: working product preparing for its first hospital pilots. November 2026.*

---

## 1. What ClaustraRCM does

ClaustraRCM checks hospital claims **before they are submitted**, so preventable errors are
fixed while they are still a two-minute correction rather than a denial, an appeal and weeks
of waiting for payment.

It works in three steps:

| Step | What happens |
|---|---|
| **Load** | Claims come in from a file (837P, 837I, CSV or Excel), from your systems through an API, or are entered on screen. |
| **Validate & Correct** | Every claim is checked against configurable rules and coding edits, given a 0–100 denial-risk score, and every problem is explained with a suggested fix that staff can apply or undo. |
| **Send** | A clean claim goes back to your billing system with a corrected 837 file and a list of what changed. |

ClaustraRCM is **not another billing system**. It sits alongside the one you already use.
It does **not** send claims to payers or clearinghouses today. A clearinghouse connection is
planned after the pilot.

---

## 2. What it checks

| Check | Example of what it catches |
|---|---|
| Required fields | A missing diagnosis, member ID, provider or payer |
| Prior authorization | A service on the payer's prior-authorization list with no authorization number on the claim |
| NCCI procedure-to-procedure edits | Two procedures that can't be billed together on the same day without an appropriate modifier |
| MUE limits | More units of a service in a day than Medicare allows |
| LCD/NCD coverage | A diagnosis that isn't on the covered list for the procedure it supports |
| Diagnosis/procedure fit | A specialty procedure pointing to a diagnosis from an unrelated area (e.g. an echocardiogram for diabetes). Shown as a warning. |
| Your own rules | Any rule your administrators define: field, condition and value, scoped to payers, departments or claim types |

**What a clean result does not mean.** A claim that passes has no errors that ClaustraRCM can
detect. It is not a guarantee of payment. In particular:

- **Coverage** is not verified. Confirming active coverage needs a real-time eligibility check
  (270/271) with the payer, which is planned after the pilot. Claims say "coverage not checked".
- **Prior authorization** is checked against the lists your administrators keep per payer.
  A claim showing an authorization number means one is on the claim, not that the payer
  confirmed it.

---

## 3. How it is built

```
   Your staff (web browser)              Your systems (EHR, billing)
            │                                       │
            │  HTTPS, signed-in session             │  HTTPS, API key
            ▼                                       ▼
   ┌──────────────────┐                 ┌──────────────────────┐
   │   Web application │ ───────────────▶│      ClaustraRCM API  │
   │  (what staff see) │                 │  rules · scoring ·    │
   └──────────────────┘                 │  fixes · 837 files ·  │
                                         │  audit log            │
                                         └──────────┬───────────┘
                                                    │
                          ┌─────────────────────────┼──────────────────────────┐
                          ▼                         ▼                          ▼
              ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
              │ Your organisation's  │  │ Reference code sets  │  │ Claude (Anthropic),  │
              │ data, encrypted with │  │ NCCI, MUE, LCD/NCD,  │  │ optional: writes the │
              │ its own key          │  │ CPT, ICD-10, CARC    │  │ assistant's answers  │
              └──────────────────────┘  └──────────────────────┘  │ from codes only      │
                                                                  └──────────────────────┘
```

**The web application** (the "frontend") is what staff use in their browser: the claims
queue, the claim entry form, the Overview dashboard, rule management and the audit log. It
holds no data of its own; everything comes from the API.

**The API** (the "backend") does the work: it runs the rules, scores risk, suggests fixes,
builds the 837 files and PDFs, and records every request in the audit log. Your own systems
can talk to it directly with an API key, to send claims in and receive the results.

**Your organisation's data** lives in its own separate store, walled off from every other
organisation (section 4).

**Reference code sets** (NCCI edits, MUE limits, LCD/NCD policies, CPT, ICD-10, CARC/RARC)
are shared by every organisation. They contain no patient information.

---

## 4. Security and privacy

### Each organisation is walled off

- Every account belongs to exactly one organisation and can only reach that organisation's
  data. Another organisation's records simply don't exist as far as it is concerned.
- An automated test tries every part of the API with another organisation's record IDs to
  confirm nothing leaks across.
- Each organisation's patient data is **encrypted at rest with its own key**. When an
  organisation leaves, its key is destroyed first, then its data.

### People see only what they need

| Role | Can |
|---|---|
| Analyst | See claims, results and the dashboard, without patient names or demographics |
| Biller | Also see patient details, enter and correct claims, and send them on |
| Administrator | Also manage rules, user accounts and settings, and read the audit log |

Administrators can further limit a person to particular departments, facilities or
providers (HIPAA's minimum-necessary standard). The limit applies everywhere, including the
dashboard figures and file downloads.

### Sign-in

- Passwords must be at least 12 characters with mixed case and a digit or symbol. They are
  stored only as salted hashes, and five wrong attempts lock the account for 15 minutes.
- Sessions end after 15 minutes without activity, after 8 hours, at sign-out, or when an
  account is disabled.
- Single sign-on through your identity provider (OpenID Connect: Microsoft Entra ID, Okta,
  Google) is supported per organisation and can be made the only way to sign in, with a
  designated emergency administrator account.

### Everything is recorded

- Every request is written to your organisation's **audit log**: who, what, which records,
  and the outcome (success, denied or failed).
- Each entry is chained to the one before it, so an edited or deleted entry is detected. Your
  administrators can view the log and run that check themselves.
- Entries are kept for at least six years (HIPAA's documentation period).

### Support access is visible and limited

If our team ever needs to look at your data for a support case, it requires a written reason,
is **read-only**, lasts between 15 minutes and 4 hours, shows a red banner on every page,
and can be ended early by your administrators. Every step and every request made during it
is in your audit log. Our platform administrators otherwise see no patient data.

### Your data is yours

Your administrators can export all of your organisation's data at any time as a single file,
and the export itself is recorded in the audit log.

---

## 5. The billing assistant and what it shares with AI

Staff can ask the assistant questions about a claim, such as "Why does this need a modifier?"
or "Is this diagnosis covered for this procedure?". It answers **only from the reference
records** (coverage policies, NCCI and MUE edits, payer terms, denial codes) and cites each
record it used, so every answer can be checked.

When it uses Claude (Anthropic's AI model) to write the answer, it shares **codes and amounts
only**:

| Shared | Never shared |
|---|---|
| CPT and ICD-10 codes, modifiers, units | Patient or provider names |
| Payer, claim type, place of service | Patient IDs, member IDs, NPIs, authorization numbers |
| Charges and authorization status | Age, sex, ZIP code |
| Denial codes (CARC/RARC), service year | Any date more precise than the year, or free-text notes |

Names, IDs and dates typed into a question are masked before it is sent. The screen shows
exactly what was shared. The assistant can also run with AI switched off, in which case it
returns the matching reference records instead of a written answer.

The rule-based fix suggestions ("AI Fix") don't use an AI model at all.

---

## 6. How claims get in and out

**In:**

- Upload a file: 837P, 837I, CSV or Excel (up to 200 claims, 5 MB).
- Send claims from your systems through the Claims API with an API key your administrator
  creates. Each claim comes back with its result, problems and suggested fixes. Sending the
  same claim number again replaces the earlier draft, so a corrected claim or a retry never
  creates a duplicate.
- Enter a claim on screen, with the patient's details filled in from their registration.

**Patients.** Your registration system remains the master record. ClaustraRCM keeps a
minimal working copy that claims keep up to date. Possible duplicates are flagged for staff;
nothing is merged automatically.

**Out:**

- **Hand off to your billing system** (the default): download the corrected 837 file and a
  PDF listing every change made and anything still open. Your billing system sends the claim.
- **Mark as submitted in ClaustraRCM**: allowed only once no error or warning remains. The
  837 is saved with the claim as the record of what was sent, with CMS-1500 or UB-04 PDFs
  built from it.

Your administrators choose which route is offered first.

---

## 7. Where things stand

| | Status |
|---|---|
| Validation, coding checks, risk score, fixes, assistant | Built |
| File upload, Claims API, claim entry, corrected 837 export | Built |
| Organisation separation, roles, need-to-know limits, audit log | Built |
| Encryption at rest per organisation, data export and deletion | Built |
| Single sign-on (OpenID Connect) | Built; connected per client during onboarding |
| Hosted demonstration on synthetic data | Live at https://claustrarcm-demo.vercel.app |
| Eligibility checks (270/271) | Planned after the pilot |
| Clearinghouse connection and payer remittance (835) | Planned after the pilot |

### Before any real patient data is loaded

ClaustraRCM currently runs on **synthetic data only**. Before a pilot uses real claims,
we will complete and confirm with you:

1. A signed **business associate agreement (BAA)** between your organisation and ClaustraRCM.
   The system blocks sign-in for any organisation without one on record.
2. A BAA or data processing agreement with **Anthropic**, or the assistant runs with AI
   switched off for your organisation.
3. Hosting on a production server with HTTPS, and the master encryption key held in a cloud
   key management service rather than on the server.
4. Single sign-on connected to your identity provider, if you use one.

---

## 8. Questions we can answer in a call

- Which payers and services your prior-authorization lists should cover
- How your billing system can receive the corrected 837 files
- Which denials your team sees most, so the pilot checks the right things
- Your security review: questionnaires, architecture diagrams and the audit log in detail

**Contact:** jubril.d.olalekan@gmail.com · **Request a pilot:** https://claustrarcm-demo.vercel.app/pilot
