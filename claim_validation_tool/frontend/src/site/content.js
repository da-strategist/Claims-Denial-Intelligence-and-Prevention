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
 * Names and roles from the owner; bios drawn only from each person's LinkedIn profile.
 * Without a photo, the card shows the person's initials. */
export const TEAM = [
  {
    name: 'Jubril Olalekan',
    role: 'Founder',
    bio: 'Health information management professional and data analyst. Spent three years at the Institute for Information and Communication Technology (IICT) in Nigeria helping design an electronic clinical coding system (ICD-10 and ICD-10-PCS), a disease surveillance module and an electronic health insurance system, and trained more than 100 healthcare professionals in clinical coding and health record workflows. Now brings coding and revenue cycle knowledge together with data engineering to catch claim errors before submission.',
    photo: '/team/jubril-olalekan.jpg',
    linkedin: 'https://www.linkedin.com/in/jubril-olalekan',
  },
  {
    name: 'Maureen Okonkwo',
    role: 'Co-founder',
    bio: 'Senior BI and data analyst in Melbourne, building SQL, Tableau and Power BI reporting for leadership teams in SaaS, consulting and healthcare. A two-time Tableau Ambassador and Vizzies Award winner who co-leads the Lagos Tableau User Group and mentors analysts across Africa through Women in Data Africa.',
    photo: '/team/maureen-okonkwo.jpg',
    linkedin: 'https://www.linkedin.com/in/maureencokonkwo',
  },
]

/** The founder's account of why ClaustraRCM exists, adapted from the founder's own LinkedIn writing.
 * Paragraphs are separated by a blank line. A first version, to be refined. */
export const FOUNDER_STORY = `There’s a gap in healthcare operations that often goes unnoticed. On one side are clinical coders and health information professionals, who understand ICD-10 rules, payer coverage requirements, and exactly why a claim gets denied. On the other are data and analytics engineers, who can build pipelines and dashboards but have never opened a coding manual. Both do important work, and neither speaks the other’s language fluently.

The result is denial dashboards that count problems without explaining them, and catch them only after the damage is done. A denied claim costs twice: weeks waiting on cash, and hours of rework to get it. Many denials are preventable: a missing diagnosis, two codes that can’t be billed together, a prior authorization number that never made it onto the claim.

I’ve worked on both sides. I coded clinical records, trained hospital staff, and helped design an electronic clinical coding system and an electronic health insurance system, then moved into data and analytics engineering. ClaustraRCM brings the two together: it checks every claim before submission, explains what’s wrong and how to fix it, and holds back the ones likely to be denied until someone does.

We’re starting with the hospitals that can least afford the leakage: rural and Critical Access Hospitals.

— Jubril Olalekan, Founder`

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
