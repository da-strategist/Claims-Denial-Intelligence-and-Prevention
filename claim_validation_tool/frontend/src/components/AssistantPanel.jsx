import { useId, useState } from 'react'
import { CLARIFICATION_TOPICS, INPUT_CLASS, TOPIC_QUESTIONS } from '../constants'
import { askAssistant } from '../services/api'
import { answerBlocks, inlineSegments } from '../utils/answerText'

const SOURCE_TYPE_LABELS = {
  coverage_policy: 'LCD / NCD',
  ncci_edit: 'NCCI edit',
  mue: 'MUE',
  payer: 'Payer',
  payer_contract: 'Contract',
  carc: 'CARC',
  rarc: 'RARC',
  fee_schedule: 'Fee schedule',
}

function Inline({ text, sourceId }) {
  return inlineSegments(text).map((segment, index) => {
    if (segment.bold) return <strong key={index}>{segment.bold}</strong>
    if (segment.citations) {
      return segment.citations.map((label) => (
        <a
          key={`${index}-${label}`}
          href={`#${sourceId(label)}`}
          onClick={(event) => {
            // Scroll to the source without changing the hash route
            event.preventDefault()
            document.getElementById(sourceId(label))?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
          }}
          className="mx-0.5 rounded bg-sky-100 px-1 text-xs font-semibold text-sky-800 hover:bg-sky-200"
        >
          {label}
        </a>
      ))
    }
    return <span key={index}>{segment.text}</span>
  })
}

function Answer({ text, sourceId }) {
  return (
    <div className="space-y-2 text-sm text-gray-800">
      {answerBlocks(text).map((block, index) => {
        if (block.type === 'h') {
          return (
            <h4 key={index} className="font-semibold text-gray-900">
              <Inline text={block.text} sourceId={sourceId} />
            </h4>
          )
        }
        if (block.type === 'p') {
          return (
            <p key={index}>
              <Inline text={block.text} sourceId={sourceId} />
            </p>
          )
        }
        const List = block.type === 'ol' ? 'ol' : 'ul'
        return (
          <List key={index} className={`space-y-0.5 pl-5 ${List === 'ol' ? 'list-decimal' : 'list-disc'}`}>
            {block.items.map((item, i) => (
              <li key={i}>
                <Inline text={item} sourceId={sourceId} />
              </li>
            ))}
          </List>
        )
      })}
    </div>
  )
}

function Sources({ sources, sourceId, showCited }) {
  return (
    <ol className="space-y-1.5">
      {sources.map((source) => (
        <li
          key={source.label}
          id={sourceId(source.label)}
          className={`scroll-mt-4 rounded-md border px-2.5 py-1.5 ${source.cited || !showCited ? 'border-sky-200 bg-white' : 'border-gray-100 bg-gray-50 opacity-75'}`}
        >
          <details>
            <summary className="cursor-pointer select-none text-xs">
              <span className="mr-1.5 font-semibold text-sky-800">{source.label}</span>
              <span className="font-semibold text-gray-800">{source.title}</span>
              <span className="ml-1.5 uppercase tracking-wide text-gray-400">
                {SOURCE_TYPE_LABELS[source.source_type] ?? source.source_type}
              </span>
              {showCited && !source.cited && (
                <span className="ml-1.5 text-gray-400">· not cited</span>
              )}
              <span className="block text-gray-500">{source.match_reason}</span>
            </summary>
            <p className="mt-1.5 text-xs text-gray-700">{source.excerpt}</p>
          </details>
        </li>
      ))}
    </ol>
  )
}

function SharedFacts({ facts }) {
  const lines = facts.lines
    .map((l) => `${l.cpt_code}${l.modifier ? `-${l.modifier}` : ''} ×${l.units} → ${l.icd10_pointer}`)
    .join(', ')
  const denials = facts.denials.map((d) => `CARC ${d.carc_code} / ${d.rarc_code}`).join(', ')
  return (
    <details className="text-xs text-gray-500">
      <summary className="cursor-pointer select-none hover:text-gray-800">
        What was shared about this claim
      </summary>
      <p className="mt-1">
        {facts.payer_name ?? facts.payer_id} · {facts.claim_type} · POS {facts.place_of_service} ·{' '}
        {facts.service_month} · {lines}
        {denials && ` · ${denials}`}. Codes and amounts only — no patient or provider details,
        IDs, or exact dates.
      </p>
    </details>
  )
}

/**
 * Ask the clarification assistant about a claim. Answers come from the reference tables
 * (coverage policies, NCCI/MUE edits, payer contracts, CARC/RARC codes), citing them.
 */
export default function AssistantPanel({ claimId, topic }) {
  const baseId = useId()
  const sourceId = (label) => `${baseId}-${label}`
  const [question, setQuestion] = useState(TOPIC_QUESTIONS[topic] ?? '')
  const [result, setResult] = useState(null)
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState(null)

  const ask = async (event) => {
    event.preventDefault()
    setAsking(true)
    setError(null)
    try {
      setResult(await askAssistant({ question, claimId, topic }))
    } catch (err) {
      setError(err.message)
    } finally {
      setAsking(false)
    }
  }

  return (
    <section
      aria-label="Clarification assistant"
      aria-busy={asking}
      className="space-y-3 rounded-lg border border-sky-100 bg-sky-50/40 p-3"
    >
      <form onSubmit={ask} className="space-y-2">
        <label htmlFor={`${baseId}-question`} className="block text-xs font-semibold text-sky-800">
          Ask the assistant{topic && ` · ${CLARIFICATION_TOPICS[topic]}`}
        </label>
        <textarea
          id={`${baseId}-question`}
          rows={3}
          required
          minLength={3}
          maxLength={1000}
          className={`${INPUT_CLASS} resize-y`}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={asking}
            className="rounded-lg bg-sky-700 px-3 py-1.5 text-sm font-semibold text-white hover:bg-sky-800 disabled:opacity-50"
          >
            {asking ? 'Researching…' : 'Ask'}
          </button>
          <span className="text-xs text-gray-500">
            Answers cite the reference tables. Don’t include patient names.
          </span>
        </div>
      </form>

      {error && (
        <p role="alert" className="text-sm text-red-700">
          Could not get an answer — {error}
        </p>
      )}

      {result && (
        <div className="space-y-3 border-t border-sky-100 pt-3">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span
              className={`rounded-full border px-2 py-0.5 font-semibold ${result.mode === 'claude' ? 'border-sky-200 bg-white text-sky-800' : 'border-gray-200 bg-white text-gray-600'}`}
            >
              {result.mode === 'claude' ? `Claude · ${result.model}` : 'Sources only'}
            </span>
            {result.notice && <span className="text-amber-700">{result.notice}</span>}
          </div>
          {/* Without Claude the answer only lists the sources, which are shown below anyway */}
          {(result.mode === 'claude' || result.sources.length === 0) && (
            <Answer text={result.answer} sourceId={sourceId} />
          )}
          {result.sources.length > 0 && (
            <div className="space-y-1.5">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Sources ({result.sources.length})
              </h4>
              <Sources
                sources={result.sources}
                sourceId={sourceId}
                showCited={result.mode === 'claude'}
              />
            </div>
          )}
          {result.claim_facts && <SharedFacts facts={result.claim_facts} />}
        </div>
      )}
    </section>
  )
}
