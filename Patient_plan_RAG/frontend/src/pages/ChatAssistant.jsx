import React, { useEffect, useState, useRef } from "react";
import { api } from "../services/api";

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

export default function ChatAssistant() {
  const [policies, setPolicies] = useState([]);
  const [selectedPolicy, setSelectedPolicy] = useState("");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const messagesEnd = useRef(null);

  useEffect(() => {
    api.listPolicies().then((p) => {
      setPolicies(p);
      if (p.length > 0) setSelectedPolicy(p[0].document_id);
    });
  }, []);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleAsk = async () => {
    if (!question.trim()) return;
    const q = question.trim();
    setQuestion("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);

    try {
      const resp = await api.chat(q, selectedPolicy || undefined);
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
        <select
          value={selectedPolicy}
          onChange={(e) => setSelectedPolicy(e.target.value)}
          className="border rounded px-3 py-1.5 text-sm"
        >
          <option value="">All policies</option>
          {policies.map((p) => (
            <option key={p.document_id} value={p.document_id}>
              {p.filename}
            </option>
          ))}
        </select>
      </div>

      <div className="flex-1 overflow-y-auto bg-white rounded-lg shadow p-4 space-y-4">
        {messages.length === 0 && (
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

      <div className="mt-3 flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleAsk()}
          placeholder="Ask about coverage, costs, prior authorization..."
          className="flex-1 border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={loading}
        />
        <button
          onClick={handleAsk}
          disabled={loading || !question.trim()}
          className="bg-blue-600 text-white px-5 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          Ask
        </button>
      </div>
    </div>
  );
}
