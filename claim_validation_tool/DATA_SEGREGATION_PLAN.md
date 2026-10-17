# Data segregation plan: organisations and need-to-know access

**Status:** design agreed 2026-10-17 (decisions in §8) — not built yet.
**Goal:** many organisations (hospitals, practices) can use one hosted ClaustraRCM, each
completely walled off from the others; inside each organisation, people see only the
facilities, departments, or providers they work for (HIPAA's minimum necessary standard).

---

## 1. Where we are

The tool serves one organisation. Roles limit *what kind* of thing a user can do (analysts
don't see patient details; only billers and admins change claims), but every user sees
every claim, patient, draft, and dashboard figure. Every store is a single file and every
cache a single object:

| Kind | What | Today |
|---|---|---|
| Claims data | claims, lines, denials, patients, providers, departments, facilities, contracts | one repository over `Data/raw_data` |
| App data | rules, AI-fix corrections, saved drafts, new claims (+ their 837s), patient registrations, 837 settings | one JSON file each in `backend/` |
| Accounts | users, sessions, login throttle | one users file; sessions in memory |
| Audit | every request | one hash-chained `logs/audit.jsonl` |
| Caches | validation snapshot, knowledge base, retriever, name scrubber, reference data | one per process |
| API | 47 routes in 15 routers | none take an organisation into account |

## 2. Two levels of protection

| | Level 1 — organisation wall | Level 2 — need-to-know scope |
|---|---|---|
| Separates | different covered entities | people inside one organisation |
| Failure means | a reportable HIPAA breach between organisations | someone sees more of their own organisation than they need |
| Mechanism | each organisation's data kept **physically apart** (separate stores), chosen from the signed-in user | each user's **scope** (facilities, departments, providers) applied as a filter |

Level 1 is the foundation and is built first; level 2 sits on top.

## 3. Level 1 — the organisation wall

### 3.1 Approach: separate stores per organisation, shared code

Each organisation gets its own folder, and every store and cache is created **per
organisation**:

```
backend/orgs/
  meridian/                 # today's data becomes the first organisation
    data/                   # claims, lines, denials, patients, providers, facilities, contracts
    rules.json  claim_corrections.json  claim_drafts.json  new_claims.json
    patient_registrations.json  edi_settings.json
    logs/audit.jsonl
  lakeside/                 # a second organisation (sample data, for proving the wall)
    ...
```

Why this rather than one shared store with an `organisation_id` column on every row:

- **A missed filter can't leak.** Organisation B's claims are never in the same table as
  A's, so a page or query that forgets to filter still only sees A. With a shared table,
  one forgotten `WHERE organisation_id = …` exposes everyone.
- **It fits the current design.** Today's stores are already self-contained objects; they
  become one instance per organisation instead of one per process.
- **It makes the strongest option easy later.** Moving a large client to its own database
  or deployment is moving a folder, not untangling shared tables.

The cost is memory (each organisation's claims loaded separately) and a little more
bookkeeping; both are fine at this scale. A move to a real database later keeps the same
rule: one schema or database per organisation.

### 3.2 How a request finds its organisation

1. Each account belongs to exactly **one** organisation (`users.json` gains
   `organisation_id`).
2. At sign-in, the session records the organisation. It is never taken from the URL, a
   header, or the request body, so a user can't ask for another organisation's data.
3. One dependency, `current_org`, gives every route that organisation's stores:
   `get_repository(org)`, `get_rule_repository(org)`, `get_audit_log(org)`, and so on. The
   global `get_repository()` style getters are **removed**, so a route can't reach data
   without going through the organisation.
4. Claim, patient, draft, and rule IDs only resolve inside the organisation. Asking for
   another organisation's ID returns **404 Not found**, the same as an ID that doesn't
   exist, so nothing confirms it exists elsewhere.

### 3.3 What is shared and what isn't

| Shared (not PHI, the same for everyone) | Per organisation |
|---|---|
| Code sets: CPT, ICD-10, CARC/RARC, NCCI/MUE, LCD/NCD | Patients, registrations, claims, lines, denials, drafts, corrections |
| The payer catalogue (Medicare, Aetna, …) as names and types | Payer contracts and each payer's electronic payer ID |
| The seed rule templates | Rules (each organisation starts with the seed rules and edits its own) |
| Application code | Providers, departments, facilities, 837 settings, audit log, users |

The assistant's knowledge base is split the same way: shared code-set entries plus that
organisation's own contracts; the name scrubber masks that organisation's patient and
provider names.

### 3.4 Roles across organisations

| Role | Sees patient data | Manages |
|---|---|---|
| analyst, biller, admin (as today) | only their own organisation's | admin: their organisation's users, rules, settings |
| **platform admin** (new) | **none** | organisations: create, suspend, assign the first admin |

The platform admin runs the hosted service but can't open claims or patients. If support
ever needs to look at an organisation's data, that is **break-glass access**: requested
with a reason, limited in time, and written to that organisation's audit log so their own
administrators can see it.

### 3.5 Audit

Each organisation has its own hash-chained audit log and its admins read only theirs. The
platform keeps a separate log of organisation-level actions (created, suspended,
break-glass granted). Every event records the organisation.

## 4. Level 2 — need-to-know scope inside an organisation

### 4.1 Scope

Restriction is a **per-organisation choice, not a fixed rule.** Many organisations have one
billing team that works every department, so by default **every account sees the whole
organisation**, as today. An organisation's administrator can then restrict individual
people from the Users page, by any combination of facilities, departments, and providers.
A restricted person sees a claim if it matches **any** of their limits (e.g. "Cardiology
department, plus Dr. Robinson's claims wherever they are"). Administrators are always
organisation-wide.

Examples: a cardiology biller → department Cardiology; a satellite clinic's staff →
facility Ambulatory Surgery Center; a physician reviewing their own claims → provider
Dr. Robinson.

### 4.2 Where scope applies

| Surface | Effect |
|---|---|
| Claims list, Needs attention queue, search | only in-scope claims |
| Claim detail, AI fixes, assistant, 837 and PDF downloads | 404 for out-of-scope claims |
| Overview | every figure computed over in-scope claims only |
| New Claim | providers and facilities limited to the scope; a claim can only be created inside it |
| Drafts panel | saved forms and draft claims inside the scope |
| Rules | organisation-wide (admins only, unchanged) |
| Audit log | admins only, organisation-wide (unchanged) |

Scope is enforced in the same place as the organisation wall: the repository is asked for
claims *through* the user's scope, never directly.

### 4.3 The patient register (decided: organisation-wide)

Any biller can find any registered patient in their organisation to start a claim, but
sees only the claims, history, and denials inside their scope. (Rejected: limiting the
register to patients who already have an in-scope claim, which would stop a department
entering a patient's first claim there.)

## 5. Proving it works

- **Cross-organisation test matrix:** for **every** route (47 today, and any added later
  automatically), sign in as organisation A and try organisation B's IDs; every attempt
  must return 404 or 403, and no response may contain B's IDs or names. Like the existing
  "every route requires sign-in" test, it fails as soon as a new route forgets the wall.
- **Scope tests:** the same sweep for a scoped user against out-of-scope claims; the
  Overview's figures must equal figures computed by hand over the scope.
- **A second sample organisation** ("Lakeside Family Practice": a few hundred synthetic
  patients and claims with their own providers and facility) for tests and demos.
- **Audit checks:** break-glass and organisation changes appear in the right logs.

## 6. Migration of today's data

1. Today's data, files, and audit log move to `backend/orgs/meridian/` (the organisation
   "Meridian Regional Medical Center"); the audit log's hash chain is continued, not
   restarted.
2. Every existing account (including `jubril`) joins Meridian with its current role and
   an organisation-wide scope, so nothing changes for current users.
3. A platform admin is created on the command line.
4. The command-line tool gains `--org` for creating accounts in a given organisation.

## 7. Build phases

| Phase | Delivers | Size |
|---|---|---|
| A | Organisation wall: per-organisation stores and caches, sessions carry the organisation, `current_org` everywhere, migration of today's data, second sample organisation, cross-organisation test matrix | Large |
| B | Need-to-know scope: scope on accounts, enforced in the repository, applied to every surface in §4.2, scope editing on the Users page, scope tests | Medium |
| C | Platform administration: organisations page (create, suspend, first admin), platform audit log, break-glass access | Medium |
| D | Hardening for go-live: per-organisation encryption keys at rest, option of a separate deployment per client, BAA per organisation, data export and deletion when an organisation leaves | Ongoing |

Each phase ends with all tests passing and is committed separately.

## 8. Decisions (agreed 2026-10-17)

1. **Sign-in identity:** usernames are unique across all organisations; sign-in stays as
   it is.
2. **Patient register:** organisation-wide; claims scoped (§4.3).
3. **Scope:** a per-organisation choice. Everyone sees the whole organisation by default;
   each organisation's administrator may restrict individuals by facility, department,
   and/or provider from the Users page (§4.1).
4. **Platform access:** none by default; break-glass only, with a reason, time-limited, and
   written to the organisation's own audit log (§3.4).
5. **Second sample organisation:** "Lakeside Family Practice", generated and marked as
   sample data, used by the tests and available for demos.
