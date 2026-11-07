// Everything on the public website that only the owner can supply or approve. Until it's
// supplied, pages show a clearly labelled placeholder rather than invented content.

/** Where pilot requests go: the form opens the visitor's email app addressed here.
 * Set VITE_PILOT_CONTACT_EMAIL at build time. Unset: the form says requests aren't open yet. */
export const pilotContactEmail = () => (import.meta.env.VITE_PILOT_CONTACT_EMAIL ?? '').trim()

/** Proposed by the website brief; shown as drafts until the founder approves them. */
export const MISSION = {
  approved: false,
  mission:
    'To make pre-submission claims validation more accessible, understandable, and effective for healthcare billing teams.',
  vision:
    'A healthcare billing environment where preventable claim errors create less administrative burden and healthcare organizations can focus more resources on serving their communities.',
}

/** Team profiles, in display order: { name, role, bio, photo (URL under /public), linkedin }.
 * Empty until the owner supplies real profiles; nothing here is invented. */
export const TEAM = []

/** The founder's own account of why ClaustraRCM exists. Empty until supplied. */
export const FOUNDER_STORY = ''

/** Published legal pages. Until they exist, /privacy and /terms say they're being prepared. */
export const LEGAL = { privacy: null, terms: null }

/** Milestones verified from the repository's history. */
export const JOURNEY = [
  { when: 'October 2026', title: 'Claims API and validation engine', detail: 'Configurable rules evaluated against every claim, with a 0–100 denial-risk score.' },
  { when: 'October 2026', title: 'Correction workflow and assistant', detail: 'AI Fix suggestions that can be applied and undone, and an assistant that cites the reference record behind each answer.' },
  { when: 'October 2026', title: 'Access controls', detail: 'Role-based sign-in, an audit log of every request, organisation-level data separation, and encryption at rest.' },
  { when: 'October 2026', title: 'Synthetic-data demonstration', detail: 'A hosted demo over synthetic claims, with file upload and manual entry.' },
  { when: 'November 2026', title: 'API intake and coding checks', detail: 'An API for hospital systems, payer prior-authorization lists, and NCCI, MUE and coverage checks on service lines.' },
]
