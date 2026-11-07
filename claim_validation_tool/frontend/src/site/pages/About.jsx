import { FOUNDER_STORY, JOURNEY, MISSION, TEAM } from '../content'
import { Link } from '../Link'

function Placeholder({ children }) {
  return (
    <div className="rounded-2xl border border-dashed border-amber-300 bg-amber-50/60 p-5 text-sm text-amber-900">
      <span className="font-semibold">Content to come. </span>
      {children}
    </div>
  )
}

function DraftLabel() {
  return (
    <span className="ml-2 rounded-full bg-amber-50 px-2 py-0.5 align-middle text-[11px] font-semibold tracking-wide text-amber-800 uppercase ring-1 ring-amber-200 ring-inset">
      Draft · pending approval
    </span>
  )
}

const VALUES = [
  ['Accuracy', 'Every finding names the rule and the reference record behind it, so it can be checked.'],
  ['Accessibility', 'Built for the billing teams of smaller and rural hospitals, not only large systems.'],
  ['Transparency', 'Clear about what each check covers and what it doesn’t, including what isn’t checked yet.'],
  ['Continuous improvement', 'Rules, reference data and checks grow with what pilot partners teach us.'],
]

function TeamMember({ member }) {
  return (
    <li className="card flex flex-col p-6 sm:flex-row sm:gap-6">
      {member.photo ? (
        <img
          src={member.photo}
          alt={`Portrait of ${member.name}`}
          loading="lazy"
          width="112"
          height="112"
          className="h-28 w-28 shrink-0 rounded-2xl object-cover"
        />
      ) : (
        <div
          aria-hidden="true"
          className="flex h-28 w-28 shrink-0 items-center justify-center rounded-2xl bg-navy text-3xl font-semibold tracking-tight text-white"
        >
          {member.name
            .split(' ')
            .map((part) => part[0])
            .join('')}
        </div>
      )}
      <div className="mt-4 sm:mt-0">
        <h3 className="text-lg font-semibold text-gray-900">{member.name}</h3>
        <p className="text-sm font-medium text-accent">{member.role}</p>
        <p className="mt-2 text-[15px] leading-relaxed text-gray-600">{member.bio}</p>
        {member.linkedin && (
          <a
            href={member.linkedin}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 inline-block text-sm font-medium text-accent hover:underline"
          >
            LinkedIn<span className="sr-only"> profile of {member.name} (opens in a new tab)</span>
          </a>
        )}
      </div>
    </li>
  )
}

export default function About() {
  return (
    <>
      <section aria-labelledby="about-title" className="mx-auto max-w-4xl px-5 pt-16 pb-12 text-center sm:px-8 sm:pt-24">
        <div className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">About ClaustraRCM</div>
        <h1 id="about-title" className="mt-4 text-4xl font-semibold tracking-tight text-balance text-gray-900 sm:text-6xl sm:leading-[1.05]">
          Better Claims Start Before Submission.
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-gray-600">
          ClaustraRCM is a pre-submission claims validation platform. It helps hospital billing teams find and correct claim errors
          before claims go to payers, starting with US rural hospitals and Critical Access Hospitals.
        </p>
      </section>

      <section aria-labelledby="story-title" className="mx-auto max-w-3xl px-5 pb-20 sm:px-8">
        <h2 id="story-title" className="text-2xl font-semibold tracking-tight text-gray-900">Why it exists</h2>
        {FOUNDER_STORY ? (
          <div className="mt-4 space-y-4 text-[17px] leading-relaxed text-gray-700">
            {FOUNDER_STORY.split('\n\n').map((paragraph) => (
              <p key={paragraph.slice(0, 40)}>{paragraph}</p>
            ))}
          </div>
        ) : (
          <div className="mt-4">
            <Placeholder>The founder’s account of why ClaustraRCM was built will appear here.</Placeholder>
          </div>
        )}
      </section>

      <section aria-labelledby="mission-title" className="bg-navy py-20 sm:py-24">
        <div className="mx-auto grid max-w-6xl gap-6 px-5 sm:px-8 md:grid-cols-2">
          <h2 id="mission-title" className="sr-only">Mission and vision</h2>
          {[
            ['Our Mission', MISSION.mission],
            ['Our Vision', MISSION.vision],
          ].map(([title, text]) => (
            <div key={title} className="rounded-[1.5rem] bg-navy-soft/70 p-7 ring-1 ring-white/10 sm:p-9">
              <h3 className="text-xs font-semibold tracking-[0.16em] text-sky-300 uppercase">
                {title}
                {!MISSION.approved && <DraftLabel />}
              </h3>
              <p className="mt-4 text-xl leading-relaxed text-white sm:text-2xl">{text}</p>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="values-title" className="py-20 sm:py-24">
        <div className="mx-auto max-w-6xl px-5 sm:px-8">
          <h2 id="values-title" className="text-center text-3xl font-semibold tracking-tight text-gray-900 sm:text-4xl">Our Values</h2>
          <ol className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {VALUES.map(([title, text], index) => (
              <li key={title} className="card p-6">
                <span className="text-4xl font-semibold tracking-tight text-accent/25">{String(index + 1).padStart(2, '0')}</span>
                <h3 className="mt-3 text-lg font-semibold text-gray-900">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-gray-600">{text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section aria-labelledby="team-title" className="bg-white py-20 sm:py-24">
        <div className="mx-auto max-w-4xl px-5 sm:px-8">
          <h2 id="team-title" className="text-center text-3xl font-semibold tracking-tight text-gray-900 sm:text-4xl">Meet the Team</h2>
          {TEAM.length > 0 ? (
            <ul className="mt-12 space-y-4">
              {TEAM.map((member) => (
                <TeamMember key={member.name} member={member} />
              ))}
            </ul>
          ) : (
            <div className="mt-10">
              <Placeholder>Team profiles will appear here once they’re provided.</Placeholder>
            </div>
          )}
        </div>
      </section>

      <section aria-labelledby="journey-title" className="py-20 sm:py-24">
        <div className="mx-auto max-w-3xl px-5 sm:px-8">
          <h2 id="journey-title" className="text-center text-3xl font-semibold tracking-tight text-gray-900 sm:text-4xl">Our Journey</h2>
          <ol className="relative mt-12 space-y-8 border-l border-gray-200 pl-8">
            {JOURNEY.map((step) => (
              <li key={step.title} className="relative">
                <span aria-hidden="true" className="absolute top-1.5 -left-[2.4rem] h-3 w-3 rounded-full bg-green-600 ring-4 ring-[#f8fafc]" />
                <div className="text-xs font-semibold tracking-wide text-gray-500 uppercase">{step.when}</div>
                <h3 className="mt-1 text-lg font-semibold text-gray-900">{step.title}</h3>
                <p className="mt-1 text-[15px] leading-relaxed text-gray-600">{step.detail}</p>
              </li>
            ))}
            <li className="relative">
              <span aria-hidden="true" className="absolute top-1.5 -left-[2.4rem] h-3 w-3 rounded-full bg-accent ring-4 ring-accent/20" />
              <div className="text-xs font-semibold tracking-wide text-accent uppercase">Now</div>
              <h3 className="mt-1 text-lg font-semibold text-gray-900">Recruiting hospital pilot partners</h3>
              <p className="mt-1 text-[15px] leading-relaxed text-gray-600">
                Eligibility checks, the clearinghouse connection and payer remittance (835) follow the pilot.
              </p>
            </li>
          </ol>
        </div>
      </section>

      <section aria-labelledby="invite-title" className="px-5 pb-24 sm:px-8">
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-5 rounded-[1.75rem] bg-navy px-6 py-12 text-center sm:px-12">
          <h2 id="invite-title" className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
            Shape ClaustraRCM with us.
          </h2>
          <p className="max-w-xl text-[17px] text-slate-300">
            Pilot partners use ClaustraRCM on their own claims and help decide what it checks next.
          </p>
          <Link href="/pilot" className="btn-primary px-6 py-3 text-base">
            Request a Pilot
          </Link>
        </div>
      </section>
    </>
  )
}
