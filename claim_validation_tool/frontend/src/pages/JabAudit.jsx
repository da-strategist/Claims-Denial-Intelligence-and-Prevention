import ApiContractCard from '../components/ApiContractCard'
import { ArchitectureCards, WorkflowDiagram } from '../components/JabWorkflow'
import { useJabContracts } from '../hooks/useJab'

function Section({ title, subtitle, children }) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
        {subtitle && <p className="text-sm text-gray-500">{subtitle}</p>}
      </div>
      {children}
    </section>
  )
}

export default function JabAudit() {
  const { data: contracts, loading, error } = useJabContracts()

  return (
    <div className="space-y-8 p-4 sm:p-6">
      <div className="space-y-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">JAB Audit Integration</h1>
          <p className="text-sm text-gray-500">
            Pre-submission validation joined with post-payment underpayment recovery
          </p>
        </div>
        <div
          role="note"
          className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"
        >
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
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
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
    </div>
  )
}
