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
  const canAsk = hospital ? Boolean(selectedPatient) : Boolean(selectedPolicy) || user?.role === "individual";

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const startNewConversation = () => {
    setConversationId(null);
    setMessages([]);
  };

  const handleAsk = async () => {
    if (!question.trim() || !canAsk) return;
    const q = question.trim();
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
          citations: resp.citations,
          followUps: resp.follow_up_suggestions,
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

      <div className="flex-1 overflow-y-auto bg-white rounded-lg shadow p-4 space-y-4">
        {hospital && !selectedPatient && (
          <p className="text-sm text-gray-500">
            Choose a patient to ask about their coverage. Questions only ever search one
            patient's documents.
          </p>
        )}
        {messages.length === 0 && (!hospital || selectedPatient) && (
          <div className="text-gray-400 text-center py-12">
            <p className="text-4xl mb-3">💬</p>
            <p>Ask a question about your insurance policy.</p>
            <p className="text-sm mt-1">
              For example: "Does this plan cover MRI scans?" or "What is my
              deductible?"
            </p>
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
              <p className="whitespace-pre-line text-sm">{m.content}</p>
              {m.citations?.length > 0 && (
                <div className="mt-3 space-y-2">
                  <p className="text-xs font-semibold text-gray-600">
                    Sources:
                  </p>
                  {m.citations.map((c, j) => (
                    <Citation key={j} citation={c} index={j} />
                  ))}
                </div>
              )}
              {m.followUps?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1">
                  {m.followUps.map((f, j) => (
                    <button
                      key={j}
                      onClick={() => setQuestion(f)}
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
          onClick={handleAsk}
          disabled={loading || !question.trim() || !canAsk}
          className="bg-blue-600 text-white px-5 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          Ask
        </button>
      </div>
    </div>
  );
}
