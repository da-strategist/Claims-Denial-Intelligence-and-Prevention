import React, { useEffect, useState, useRef } from "react";
import { api } from "../services/api";
import { useAuth } from "../auth/AuthContext";
import { isHospital, usePolicyOptions } from "../hooks/usePolicyOptions";

/** Patient preselected by a link like #/chat?patient=<id> */
function patientFromHash() {
  const query = window.location.hash.split("?")[1] || "";
  return new URLSearchParams(query).get("patient") || "";
}

function Citation({ citation, index }) {
  return (
    <div className="bg-blue-50 border border-blue-200 rounded p-2 text-xs">
      <span className="font-semibold text-blue-700">
        [{index + 1}] Page {citation.page_number || "?"} —{" "}
        {citation.section || "General"}
      </span>
      <p className="text-gray-600 mt-1 italic">"{citation.excerpt}"</p>
      <span
        className={`text-xs px-1 rounded ${
          citation.confidence === "supported"
            ? "bg-green-100 text-green-700"
            : "bg-yellow-100 text-yellow-700"
        }`}
      >
        {citation.confidence}
      </span>
      {citation.from_scan && (
        <span className="ml-1 text-xs px-1 rounded bg-orange-100 text-orange-800"
              title="This passage was read from a scanned page by text recognition, which can misread characters.">
          From a scanned page — check the original
        </span>
      )}
    </div>
  );
}

/** Where member questions go, so nobody types personal details unawares. */
function PrivacyNotice({ mode }) {
  if (!mode) return null;
  return (
    <p className="text-xs text-gray-500 mb-2" role="note">
      {mode === "live"
        ? "Your questions and the matching policy passages are sent to Anthropic's Claude API to write the answer. Please don't include names, member IDs or other personal details."
        : "Answers are put together on this server from your plan documents; your questions are not sent to any outside service."}{" "}
      Conversations are kept for up to an hour so you can ask follow-up questions, then discarded.
    </p>
  );
}

const fmtDate = (iso) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString() : "");

/** Key numbers of the selected plan, from its summary (verbatim policy text). */
function PlanAtAGlance({ option }) {
  const [summary, setSummary] = useState(null);
  useEffect(() => {
    setSummary(null);
    if (option) api.getPolicySummary(option.id).then(setSummary).catch(() => setSummary(null));
  }, [option?.id]);
  if (!option || !summary) return null;
  const doc = option.doc;
  const rows = [
    ["Coverage", doc.effective_date || doc.expiration_date
      ? `${fmtDate(doc.effective_date)} – ${fmtDate(doc.expiration_date)}` : ""],
    ["Deductible", summary.deductible?.description],
    ["Out-of-pocket max", summary.out_of_pocket_max?.description],
    ...summary.copayments.filter((c) => c.service !== "Note").slice(0, 4).map((c) => [c.service, c.amount]),
  ].filter(([, v]) => v);
  if (rows.length === 0) return null;
  return (
    <aside aria-label="Plan at a glance" className="bg-white rounded-lg shadow p-4 text-sm mb-3">
      <p className="font-semibold mb-2">{option.label} at a glance</p>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1">
        {rows.map(([k, v]) => (
          <React.Fragment key={k}>
            <dt className="text-gray-500">{k}</dt>
            <dd className="text-gray-800">{v}</dd>
          </React.Fragment>
        ))}
      </dl>
      <p className="text-xs text-gray-400 mt-2">Quoted from your policy document; ask for details below.</p>
    </aside>
  );
}

function NextSteps({ steps }) {
  return (
    <div className="mt-3 bg-white/70 border border-blue-100 rounded p-2">
      <p className="text-xs font-semibold text-gray-600 mb-1">What to check</p>
      <ul className="space-y-1">
        {steps.map((s, i) => (
          <li key={i} className="text-xs text-gray-700">
            {s.text}{" "}
            <span className="text-gray-400">(based on page {s.page_number || "?"}, {s.section || "policy"})</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// the headline amount of a policy line ("Individual In-Network: $1,500 per ..." → "$1,500")
const headline = (value) => (value.match(/\$[\d,]+(?:\.\d+)?|\d+(?:\.\d+)?\s*%/) || [value])[0];

/** Plans whose amounts differ for what was asked (full wording is in the quotes below). */
function Differences({ items }) {
  return (
    <div role="note" aria-label="Plans differ" className="mt-2 bg-amber-50 border border-amber-200 rounded p-2 text-xs">
      <p className="font-semibold text-amber-900 mb-1">Your plans differ on this</p>
      {items.map((d) => (
        <p key={d.topic}>
          <span className="font-medium">{d.topic}:</span>{" "}
          {d.values.map((v) => `${v.document_name}: ${headline(v.value)}`).join(" · ")}
        </p>
      ))}
    </div>
  );
}

/** "What your policy says": verbatim passages, grouped by plan. */
function PolicySays({ quotes, whose }) {
  const plans = [...new Set(quotes.map((q) => q.document_id))];
  return (
    <div className="mt-2 space-y-2">
      {plans.map((id) => {
        const mine = quotes.filter((q) => q.document_id === id);
        return (
          <section key={id} aria-label={`What ${mine[0].document_name || "the policy"} says`}>
            <p className="text-xs font-semibold text-gray-600">
              What {plans.length > 1 ? mine[0].document_name || "this plan" : `${whose} policy`} says
            </p>
            {mine.map((q, i) => (
              <blockquote key={i} className="border-l-2 border-blue-300 pl-2 my-1 text-sm">
                “{q.quote}”
                <span className="block text-xs text-gray-500">
                  {q.document_name ? `${q.document_name} · ` : ""}page {q.page_number || "?"} · {q.section}
                  {q.from_scan && <span className="ml-1 text-orange-800">· from a scanned page, check the original</span>}
                </span>
              </blockquote>
            ))}
          </section>
        );
      })}
    </div>
  );
}

function KeepInMind({ text }) {
  return (
    <div role="note" aria-label="Keep in mind" className="mt-3 bg-white/70 border border-gray-200 rounded p-2 text-xs text-gray-600">
      <p className="font-semibold text-gray-700 mb-0.5">Keep in mind</p>
      {text}
    </div>
  );
}

export default function ChatAssistant() {
  const { user } = useAuth();
  const hospital = isHospital(user);
  const { options, patients, error: policyError } = usePolicyOptions();
  const [selectedPolicy, setSelectedPolicy] = useState("");
  const [selectedPatient, setSelectedPatient] = useState(patientFromHash);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  // Server-side conversation; follow-up questions send it back for context
  const [conversationId, setConversationId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState(null);
  const messagesEnd = useRef(null);

  useEffect(() => {
    api.health().then((h) => setMode(h.mode)).catch(() => setMode(null));
  }, []);

  // Individuals default to the first of their documents (or a sample); the
  // platform admin to the first sample. Hospital staff pick a patient first.
  // Applied once, when the list first loads, so choosing "All my documents"
  // (an empty selection) sticks.
  const defaulted = useRef(false);
  useEffect(() => {
    if (defaulted.current || hospital || options.length === 0) return;
    defaulted.current = true;
    setSelectedPolicy(options[0].id);
  }, [hospital, options]);

  const patientDocs = options.filter((o) => {
    if (!selectedPatient) return false;
    const patient = patients.find((p) => p.patient_id === selectedPatient);
    return patient?.documents.some((d) => d.document_id === o.id);
  });
  const policyChoices = hospital ? patientDocs : options;
  const selectedOption = options.find((o) => o.id === selectedPolicy);

  // Starter questions built from the documents in scope
  const [starters, setStarters] = useState([]);
  useEffect(() => {
    if (hospital && !selectedPatient) return setStarters([]);
    api.chatSuggestions(selectedPolicy || undefined, hospital ? selectedPatient : undefined)
      .then((r) => setStarters(r.questions))
      .catch(() => setStarters([]));
  }, [hospital, selectedPolicy, selectedPatient]);
  const canAsk = hospital ? Boolean(selectedPatient) : Boolean(selectedPolicy) || user?.role === "individual";

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const startNewConversation = () => {
    setConversationId(null);
    setMessages([]);
  };

  /** Ask the typed question, or `text` (a suggested question, sent as is). */
  const handleAsk = async (text) => {
    const q = (typeof text === "string" ? text : question).trim();
    if (!q || !canAsk || loading) return;
    setQuestion("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);

    try {
      const resp = await api.chat(q, selectedPolicy || undefined, conversationId,
                                  hospital ? selectedPatient : undefined);
      setConversationId(resp.conversation_id || null);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: resp.answer,
          lead: resp.lead || "",
          policySays: resp.policy_says || [],
          differences: resp.differences || [],
          keepInMind: resp.keep_in_mind || "",
          citations: resp.citations,
          followUps: resp.follow_up_suggestions,
          nextSteps: resp.next_steps || [],
        },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${e.message}`, citations: [] },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-200px)]">
      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-2xl font-bold">Ask a Question</h2>
        {hospital && (
          <select
            aria-label="Patient"
            value={selectedPatient}
            onChange={(e) => {
              // a conversation is about one patient
              setSelectedPatient(e.target.value);
              setSelectedPolicy("");
              startNewConversation();
            }}
            className="border rounded px-3 py-1.5 text-sm"
          >
            <option value="">Choose a patient…</option>
            {patients.map((p) => (
              <option key={p.patient_id} value={p.patient_id}>
                {p.name}{p.reference ? ` (${p.reference})` : ""}
              </option>
            ))}
          </select>
        )}
        <select
          aria-label="Policy"
          value={selectedPolicy}
          disabled={hospital && !selectedPatient}
          onChange={(e) => {
            // a conversation is scoped to one policy
            setSelectedPolicy(e.target.value);
            startNewConversation();
          }}
          className="border rounded px-3 py-1.5 text-sm"
        >
          {hospital && <option value="">All of this patient's documents</option>}
          {user?.role === "individual" && <option value="">All my documents</option>}
          {policyChoices.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
        {policyError && (
          <p className="text-xs text-red-600 mt-1">Couldn't load policies: {policyError}</p>
        )}
        <button
          onClick={startNewConversation}
          disabled={loading || messages.length === 0}
          className="ml-auto border px-3 py-1.5 rounded text-sm hover:bg-gray-50 disabled:opacity-50"
        >
          New conversation
        </button>
      </div>

      <PlanAtAGlance option={selectedOption} />
      <div className="flex-1 overflow-y-auto bg-white rounded-lg shadow p-4 space-y-4">
        {hospital && !selectedPatient && (
          <p className="text-sm text-gray-500">
            Choose a patient to ask about their coverage. Questions only ever search one
            patient's documents.
          </p>
        )}
        {messages.length === 0 && (!hospital || selectedPatient) && (
          <div className="text-center py-8">
            <p className="text-4xl mb-3">💬</p>
            <p className="text-gray-500">Ask a question about {hospital ? "this patient's" : "your"} insurance policy.</p>
            {starters.length > 0 && (
              <div className="mt-4 flex flex-wrap justify-center gap-2 max-w-2xl mx-auto" aria-label="Suggested questions">
                {starters.map((q) => (
                  <button key={q} onClick={() => handleAsk(q)}
                          className="text-sm bg-blue-50 text-blue-800 px-3 py-1.5 rounded-full border border-blue-200 hover:bg-blue-100">
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg p-3 ${
                m.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              {m.policySays?.length > 0 ? (
                <>
                  {/* live answers are written explanations; demo answers lead into the quotes */}
                  <p className="whitespace-pre-line text-sm">
                    {mode === "live" ? m.content.replace(m.keepInMind, "").replace(/\u26a0\ufe0f\s*$/, "").trim() : m.lead}
                  </p>
                  {m.differences?.length > 0 && <Differences items={m.differences} />}
                  <PolicySays quotes={m.policySays} whose={hospital ? "the patient's" : "your"} />
                </>
              ) : (
                <p className="whitespace-pre-line text-sm">{m.content}</p>
              )}
              {m.nextSteps?.length > 0 && <NextSteps steps={m.nextSteps} />}
              {m.keepInMind && <KeepInMind text={m.keepInMind} />}
              {m.citations?.length > 0 && (
                <details className="mt-3">
                  <summary className="text-xs font-semibold text-gray-600 cursor-pointer">
                    All sources ({m.citations.length})
                  </summary>
                  <div className="mt-2 space-y-2">
                    {m.citations.map((c, j) => (
                      <Citation key={j} citation={c} index={j} />
                    ))}
                  </div>
                </details>
              )}
              {m.followUps?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1">
                  {m.followUps.map((f, j) => (
                    <button
                      key={j}
                      onClick={() => handleAsk(f)}
                      className="text-xs bg-white/80 text-blue-700 px-2 py-1 rounded border border-blue-200 hover:bg-blue-50"
                    >
                      {f}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-lg p-3 text-sm text-gray-500 animate-pulse">
              Searching policy documents...
            </div>
          </div>
        )}
        <div ref={messagesEnd} />
      </div>

      <div className="mt-3">
        <PrivacyNotice mode={mode} />
      </div>
      <div className="flex gap-2">
        <input
          value={question}
          maxLength={2000}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleAsk()}
          placeholder="Ask about coverage, costs, prior authorization..."
          className="flex-1 border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={loading}
        />
        <button
          onClick={() => handleAsk()}
          disabled={loading || !question.trim() || !canAsk}
          className="bg-blue-600 text-white px-5 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          Ask
        </button>
      </div>
    </div>
  );
}
