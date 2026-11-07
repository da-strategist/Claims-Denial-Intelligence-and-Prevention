# CLAUSTRARCM — PREMIUM WEBSITE DESIGN & DEVELOPMENT MASTER PROMPT

## YOUR ROLE

You are an elite multidisciplinary team consisting of:

- A world-class product designer.
- A senior UI/UX engineer.
- A healthcare SaaS brand strategist.
- A conversion-focused website designer.
- A senior React and FastAPI developer.
- A specialist in human-centered design and visual storytelling.

Your assignment is to design and implement a premium, visually striking, highly professional website for **ClaustraRCM**, a healthcare claims validation platform.

This is not a request to create a generic SaaS landing page.

The objective is to create a memorable product experience that communicates ClaustraRCM's value almost instantly.

**The claims validation workflow must be the visual centerpiece of the entire homepage.**

Visitors should see the product working before they need to read detailed explanations.

The design philosophy should draw from the principles associated with Steve Jobs and Apple's best product presentations:

- Radical simplicity.
- One powerful idea at a time.
- Show rather than tell.
- Product-first storytelling.
- Exceptional visual hierarchy.
- Minimal cognitive friction.
- Meticulous attention to detail.
- Emotional resonance through clarity and usefulness.

Do not imitate Apple's branding, layouts, or proprietary visual assets. Apply the underlying principles to create an original ClaustraRCM identity.

The finished website must feel credible to hospital CFOs, revenue-cycle directors, billing managers, and healthcare administrators.

---

# 1. MANDATORY: INSPECT THE EXISTING PROJECT FIRST

Before designing or implementing anything, thoroughly inspect the actual ClaustraRCM project directory.

The repository is the authoritative source of truth.

Do not rely solely on descriptions provided in this prompt.

Review:

- Project folder structure.
- Frontend dependencies and package configuration.
- Backend dependencies and Python environment.
- Existing React components and routing.
- Existing Tailwind styling and design tokens.
- Existing authentication and organization management.
- Existing ClaustraRCM branding and logo assets.
- Claims validation engine and business rules.
- Claims intake methods.
- Clean and unclean claim classification.
- Claim correction and revalidation workflow.
- Claims submission or export capabilities.
- Dashboard components and Recharts visualizations.
- AI billing assistant capabilities.
- Data storage and persistence.
- File upload implementation.
- API endpoints.
- Existing environment configuration.
- Deployment configuration.
- Tests and build scripts.

The application has previously been described as using:

- React and Vite.
- Tailwind CSS.
- Recharts.
- Python, FastAPI, and Uvicorn.
- pandas.
- Anthropic SDK.
- Organization-specific JSON file storage.
- Vercel for frontend hosting.
- Fly.io for backend hosting.

These details must be verified against the actual project.

If the repository differs, follow the repository.

**Do not invent functionality or silently rewrite working systems.**

Before making changes, provide a concise technical assessment of the existing stack, available functionality, and planned implementation.

---

# 2. PRODUCT UNDERSTANDING

ClaustraRCM is a pre-submission healthcare claims validation platform.

Its purpose is to help hospital billing teams identify and correct errors before submitting claims to insurance payers.

It supports three claim intake methods:

1. API integration.
2. Manual claim entry.
3. File upload.

Claims are evaluated against applicable validation rules, including coding, completeness, and payer-specific checks.

The platform classifies claims as:

**Clean:** The claim passes configured validation checks.

**Unclean:** The claim requires review and correction by a billing specialist.

After correction, the claim can be revalidated.

A clean claim is not a guarantee of insurer acceptance or payment.

The product currently has a working demonstration using synthetic data and is preparing for its first hospital pilot.

The initial target market is US rural hospitals and Critical Access Hospitals.

Do not imply the platform has existing hospital customers, proven reimbursement improvements, or completed hospital pilots.

---

# 3. BRAND STRATEGY

## Core Brand Positioning

**ClaustraRCM — Better Claims Start Before Submission.**

This should be the central brand idea.

The website must position ClaustraRCM as:

- Intelligent but understandable.
- Sophisticated but easy to use.
- Professional but approachable.
- Innovative but practical.
- Designed to support billing professionals, not replace their judgment.

## Primary Homepage Headline

**Catch Claim Errors Before They Become Costly Rework.**

Supporting copy:

"Load your claims. Identify and correct errors. Move validated claims forward — all through one streamlined workflow."

## Brand Personality

Confident, precise, calm, trustworthy, modern, and human-centered.

Avoid exaggerated marketing language.

Do not make unsupported claims about financial savings, accuracy percentages, security certifications, or guaranteed reimbursement.

---

# 4. VISUAL DESIGN DIRECTION

Create a premium healthcare technology design system.

Suggested palette:

- Deep navy: `#0B1730`
- Primary blue: `#2563EB`
- Teal: `#0D9488`
- Soft white: `#F8FAFC`
- Slate gray: `#64748B`
- Clean status green: `#16A34A`
- Review status amber: `#D97706`

Inspect existing brand assets before deciding whether to use these colors.

Use professional typography such as Inter, Manrope, or Plus Jakarta Sans.

Visual characteristics:

- Large, compelling headlines.
- Generous whitespace.
- Clear contrast.
- Premium dashboard compositions.
- Sophisticated cards.
- Carefully controlled gradients.
- Subtle animation.
- Smooth transitions.
- Consistent iconography.
- Professional healthcare administration photography.
- Strong responsive layouts.

Avoid generic AI robots, excessive glowing graphics, unnecessary animations, and generic hospital imagery unrelated to billing.

The product UI itself should be the primary visual asset.

---

# 5. NAVIGATION

Create three main navigation destinations:

**Home | About | Sign In / Sign Up**

Include the ClaustraRCM logo and a prominent **Request a Pilot** button.

Use a sticky navigation bar with a refined scrolling state.

On mobile, provide an accessible collapsible menu.

All navigation links and CTAs must work.

---

# 6. HOME PAGE — THE PRODUCT IS THE HERO

This is the most important requirement.

The homepage must not rely on a static stock photograph or generic illustration as its hero visual.

**The hero must feature a visually compelling, interactive demonstration of the actual ClaustraRCM claims validation workflow.**

The primary narrative is:

# LOAD → VALIDATE & CORRECT → SEND

The entire homepage should be designed around this simple three-step experience.

## 6.1 Hero Section

Use a spacious, premium split-screen or integrated hero layout.

### Headline

**Catch Claim Errors Before They Become Costly Rework.**

### Supporting Text

"ClaustraRCM helps hospital billing teams validate claims before submission, identify issues that need attention, and correct errors through a clear, streamlined workflow."

### Primary CTA

**Explore the Demo**

### Secondary CTA

**Request a Pilot**

### Product Status

"Working Product | Early Hospital Pilot Phase"

### Hero Visual: Living Claims Validation Dashboard

Create an animated, interactive product visualization based on the actual ClaustraRCM interface.

The visualization should demonstrate a complete claims validation journey.

It must include:

- A claim being loaded.
- The validation engine evaluating the claim.
- A claim being flagged as unclean.
- An understandable error explanation.
- A billing specialist correcting the issue.
- The claim being revalidated.
- The claim receiving a clean status.
- The validated claim moving toward submission.

The animation should feel like a sophisticated enterprise product demonstration, not a cartoon.

Use realistic but entirely synthetic claim data.

Prefer actual UI components, screenshots, or accurate reproductions derived from the existing application.

Do not invent product capabilities.

### Interaction Requirements

Allow visitors to interact with the demonstration.

For example:

- Select a sample claim.
- Click "Validate Claim."
- View a simulated validation result.
- Inspect a highlighted error.
- Click "Correct."
- Revalidate the corrected claim.
- See the clean status.
- Proceed to the final submission-readiness stage.

This can be a frontend-only interactive demonstration using synthetic data.

It must not require authentication or access to real claims.

Clearly label simulated results as demonstration data.

If the repository supports a suitable synthetic-data demo API, it may be reused safely, but do not expose production endpoints or sensitive information.

### Motion

Use subtle animation to communicate transitions:

- Claim enters the workspace.
- Validation progress begins.
- Error is highlighted.
- Correction is applied.
- Status changes from unclean to clean.
- Claim moves forward.

Animations should be lightweight, accessible, and respectful of reduced-motion preferences.

Do not autoplay an endlessly distracting sequence.

The visual should communicate the workflow even if animation is disabled.

---

# 7. THREE SIMPLE STEPS — SIGNATURE HOMEPAGE SECTION

Immediately after the hero and its introductory context, create a large, visually distinctive section titled:

# Three Simple Steps. Clearer Claims.

Supporting copy:

"From loading a claim to preparing it for submission, ClaustraRCM keeps the process straightforward."

This must be a signature visual section, not three ordinary feature cards.

## STEP 01 — LOAD

### Headline

**Bring Your Claims In.**

Description:

"Use API integration, file upload, or manual entry to bring claims into ClaustraRCM."

### Visual

Show three input pathways:

- API.
- File upload.
- Manual entry.

These should converge into one validation workspace.

Use recognizable interface elements and subtle directional animation.

## STEP 02 — VALIDATE & CORRECT

### Headline

**Find Errors. Fix Them. Move Forward.**

Description:

"ClaustraRCM checks claims against configured rules and flags issues for billing specialists to review and correct."

### Visual

This should be the strongest visual moment of the section.

Show a realistic claim moving through the validation engine.

Present two possible results:

**Clean — Passed Validation**

**Unclean — Review Required**

Show an example unclean claim with a clearly explained error.

Demonstrate the correction and revalidation process.

Use visual cues such as highlighted fields, status changes, and a clean validation confirmation.

Do not imply that all possible claim errors can be detected.

## STEP 03 — SEND

### Headline

**Ready for the Next Step.**

Description:

"Once validated, claims can move forward through the hospital's established submission workflow."

### Visual

Show a clean claim proceeding toward a submission or export stage.

**Critical requirement:** Inspect the actual codebase to establish whether ClaustraRCM directly submits claims to payers or clearinghouses.

If direct submission is implemented, accurately show that capability.

If direct submission is not implemented, retain the simple three-step label "SEND" but clearly communicate that the claim is ready for submission through the hospital's existing process.

Never fabricate a direct payer-submission capability.

## Visual Storytelling Requirements

Use a connected visual system.

The three steps should feel like one continuous journey.

On desktop, consider an elegant horizontal sequence with animated connectors and product UI panels.

On mobile, use a vertical sequence with clear progression.

The visitor should understand the workflow within ten seconds.

---

# 8. PROBLEM SECTION

Headline:

**A Small Claim Error Shouldn't Create a Big Workflow Problem.**

Explain the consequences of preventable claim errors:

- Rejected submissions.
- Repeated corrections.
- Processing delays.
- Administrative workload.

Use concise copy and meaningful illustrations.

Do not fabricate statistics.

---

# 9. PRODUCT SHOWCASE

Headline:

**See ClaustraRCM in Action.**

Showcase the actual application using screenshots or reusable product UI components.

Potential views include:

- Claims dashboard.
- Validation results.
- Error explanations.
- Claim correction workflow.
- Reporting dashboard.
- AI billing assistant, if relevant and verified.

Use an elegant tabbed interface or carousel.

Each view should have a concise benefit-focused description.

Use synthetic data exclusively.

Provide a functioning link to the existing hosted demo once the URL is confirmed.

---

# 10. KEY FEATURES

Headline:

**Powerful Validation. Practical Workflows.**

Highlight verified functionality:

- Pre-submission validation.
- Coding checks.
- Claim completeness checks.
- Payer-specific rules.
- Clean and unclean classification.
- Claim review and correction.
- API integration.
- Manual entry.
- File upload.
- Validation reporting.
- AI-assisted billing support, where verified.

Use an elegant feature grid with meaningful visuals.

Do not overwhelm the page with technical detail.

---

# 11. BUILT FOR HOSPITAL TEAMS

Headline:

**Designed Around the People Behind Every Claim.**

Present three audiences.

### Billing Specialists

Identify errors earlier and manage corrections clearly.

### Revenue Cycle Leaders

Understand validation outcomes and recurring claim-quality issues.

### Hospital Finance Teams

Explore opportunities to reduce avoidable billing rework.

Use appropriate healthcare administration imagery.

Avoid generic clinical photography that does not relate to billing operations.

---

# 12. PRODUCT DEVELOPMENT STATUS

Headline:

**Built. Demonstrated. Preparing for Hospital Pilots.**

Create a polished timeline.

Show:

1. Working application — completed.
2. Synthetic-data demonstration — available.
3. Hospital pilot recruitment — current.
4. Live hospital pilot evaluation — planned.
5. Wider availability — future.

Clearly distinguish completed and planned milestones.

CTA:

**Interested in Becoming a Pilot Partner?**

---

# 13. FINAL HOMEPAGE CTA

Create a visually powerful closing section.

Headline:

**Better Claims Start Before Submission.**

Supporting text:

"Discover how ClaustraRCM could fit your billing workflow and help your team identify errors earlier."

Buttons:

**Explore the Demo**

**Request a Pilot**

---

# 14. ABOUT PAGE

The About page should establish trust, purpose, and human connection.

## About ClaustraRCM

Tell the story of why the platform exists.

Explain the problem it aims to solve and the motivation behind building a practical pre-submission validation solution.

Use authentic information supplied by the founder.

Do not invent a founding story.

## Our Mission

Proposed mission:

"To make pre-submission claims validation more accessible, understandable, and effective for healthcare billing teams."

## Our Vision

Proposed vision:

"A healthcare billing environment where preventable claim errors create less administrative burden and healthcare organizations can focus more resources on serving their communities."

Obtain founder approval before publishing these statements.

## Our Values

- Accuracy.
- Accessibility.
- Transparency.
- Continuous improvement.

Use distinctive visual treatments.

## Meet the Team

Create professional team profiles.

Before finalizing, ask the project owner for:

- Full name.
- Job title.
- Short biography.
- Professional photograph.
- LinkedIn profile URL.
- Preferred display order.

Do not invent people, credentials, photographs, or LinkedIn profiles.

If the team currently consists of one founder, design a polished founder profile.

## Our Journey

Use a visually appealing timeline of verified development milestones.

## Pilot Invitation

End with a clear invitation to explore pilot participation.

---

# 15. SIGN IN AND SIGN UP

Build premium, responsive authentication experiences.

Use a cohesive visual language based on the homepage.

## Sign In

Create a refined split-screen layout.

One side:

- ClaustraRCM branding.
- A concise product promise.
- A product workflow illustration or dashboard preview.

Other side:

- Email.
- Password.
- Show/hide password.
- Sign In.
- Forgot Password, if implemented.
- Loading and error states.

## Sign Up

Create a consistent registration interface.

Potential fields:

- Full name.
- Work email.
- Organization.
- Role.
- Password.
- Confirm password.

Inspect the existing authentication system before implementing changes.

For early hospital pilots, prefer invitation-only registration unless the project owner confirms open registration.

Public visitors should be able to request pilot participation without automatically receiving access to the claims application.

Do not create nonfunctional authentication forms.

---

# 16. PILOT INTEREST FORM

Build a professional form for interested hospitals.

Suggested fields:

- Full name.
- Work email.
- Hospital or organization.
- Job title.
- Organization type.
- Optional message.

Use appropriate validation, spam protection, and secure handling.

Do not collect patient information.

Connect the form to a real approved workflow.

If the destination is not configured, request the required information rather than pretending submissions work.

---

# 17. FOOTER

Include:

- ClaustraRCM logo.
- Short product description.
- Home.
- About.
- Sign In.
- Pilot Interest.
- Approved contact details.
- Privacy Policy.
- Terms of Use.
- Copyright.

Do not fabricate legal information.

---

# 18. ACCESSIBILITY, PERFORMANCE, AND RESPONSIVENESS

Implement:

- Mobile-first responsive design.
- Semantic HTML.
- Accessible navigation.
- Keyboard support.
- Visible focus indicators.
- Appropriate color contrast.
- Accessible forms.
- Reduced-motion support.
- Optimized images.
- Lazy loading where appropriate.
- Efficient animations.
- Clear page metadata.
- Open Graph information.
- Appropriate heading hierarchy.

Aim for strong Lighthouse accessibility and performance results.

The interactive claims demonstration must work on touchscreens and remain understandable without animation.

---

# 19. SECURITY AND PRODUCT ACCURACY

Use synthetic data for all public demonstrations.

Do not expose real patient information, secrets, API keys, or private configuration.

Do not claim:

- Guaranteed payer acceptance.
- Guaranteed reimbursement.
- Zero claim denials.
- Verified reductions in rejection rates.
- Existing hospital customers.
- Completed hospital pilots.
- HIPAA certification or compliance status without verification.

Do not connect public demonstration interactions to live patient claims.

Preserve the existing application and authentication security model unless changes are explicitly approved.

---

# 20. REQUIRED IMPLEMENTATION PROCESS

### Phase 1 — Repository Inspection

Inspect the project and verify the actual technology stack, features, routes, and assets.

Provide a concise implementation assessment.

### Source recovery note

The conversation reader truncated the latest response at Phase 2 of this section. Sections above and Phase 1 are recovered from the latest master prompt. The continuation below is reconstructed from the accessible requirements and earlier prompt in the same conversation; it is not a verbatim recovery of the missing ending.

### Phase 2 — Visual Design Concept

Present the proposed design system, homepage narrative, component hierarchy, responsive behavior, and interactive claims workflow concept. Explain how Load → Validate & Correct → Send will form one continuous visual journey. Identify information and assets needed from the project owner.

### Phase 3 — Implementation

Implement the Home page, About page, authentication experience, and pilot-interest workflow using the verified existing stack and reusable components. Keep public marketing routes separate from protected application routes. Preserve current claims validation, organization isolation, authentication, storage, API integrations, and application behavior.

Do not add unnecessary dependencies, rewrite working systems, or invent capabilities. Ask for approval before changes that alter the existing security model or working systems.

### Phase 4 — Testing

Test desktop, tablet, mobile, keyboard, touchscreen, and reduced-motion behavior. Verify the complete synthetic-data demonstration: load a claim, validate, inspect an error, correct, revalidate, receive clean status, and proceed to the accurate submission-readiness stage.

Verify navigation, CTAs, forms, error and loading states, authentication redirects, protected routes, and existing claims functionality. Run the repository's appropriate tests and build checks. Report failures or limitations honestly.

### Phase 5 — Delivery

Summarize files created and modified, routes, reusable components, backend changes, required environment variables, validation performed, remaining configuration, and information still needed from the owner.

Do not describe a form, authentication flow, or integration as functional unless it actually works.

---

# 21. INFORMATION TO REQUEST BEFORE FINALIZING

Ask for missing information instead of inventing it:

1. Official ClaustraRCM logo, approved colors, typography, and branding preferences.
2. Team members' full names, roles, biographies, photographs, LinkedIn URLs, and display order.
3. Authentic founder story and approval of proposed mission and vision.
4. Confirmed public demo URL.
5. Pilot-interest destination and approved contact details.
6. Invitation-only versus public registration preference and existing onboarding requirements.
7. Approved Privacy Policy and Terms of Use.
8. Confirmed milestones, product capabilities, and any approved evidence or metrics.

Use clearly labeled development placeholders where needed; do not publish them as factual profiles, legal text, contact details, or working integrations. If there is only one founder, create an elegant single-person profile. External LinkedIn links must use safe new-tab behavior.

Proceed with independent implementation work while awaiting missing content, and identify anything that blocks finalization.

---

# 22. FINAL DELIVERY STANDARD

Create an original, premium, credible healthcare SaaS website whose defining visual experience is the interactive Load → Validate & Correct → Send journey.

Show the product's value quickly, support billing professionals' judgment, use synthetic data, and accurately represent what the repository implements. Keep the existing application working.

