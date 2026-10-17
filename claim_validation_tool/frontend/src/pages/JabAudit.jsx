import ApiContractCard from '../components/ApiContractCard'
import PageHeader, { Page } from '../components/PageHeader'
import { ArchitectureCards, WorkflowDiagram } from '../components/JabWorkflow'
import { useJabContracts } from '../hooks/useJab'

function Section({ title, subtitle, children }) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-gray-900">{title}</h2>
        {subtitle && <p className="text-sm text-gray-500">{subtitle}</p>}
      </div>
      {children}
    </section>
  )
}

export default function JabAudit() {
  const { data: contracts, loading, error } = useJabContracts()

  return (
    <Page wide>
      <div className="space-y-4">
        <PageHeader
          title="JAB Audit"
          subtitle="Pre-submission validation joined with post-payment underpayment recovery"
        />
        <div role="note" className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <span className="font-semibold">Conceptual — not a live connection.</span> Steps marked
          Live run in this app today. Everything else is a proposed design; contract examples are
          illustrative, not claims data.
        </div>
      </div>

      <Section title="Workflow" subtitle="Where each system acts on a claim">
        <WorkflowDiagram />
      </Section>

      <Section title="Integration architecture" subtitle="Systems involved and what they exchange">
        <ArchitectureCards />
      </Section>

      <Section
        title="Proposed API contracts"
        subtitle="Request payloads, generated from the backend models so the design stays type-checked"
      >
        {error && (
          <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
            Could not load the contracts — {error}
          </div>
        )}
        {loading && !contracts && <div className="text-sm text-gray-500">Loading contracts…</div>}
        <div className="space-y-4">
          {contracts?.map((contract) => (
            <ApiContractCard key={contract.id} contract={contract} />
          ))}
        </div>
      </Section>
    </Page>
  )
}
