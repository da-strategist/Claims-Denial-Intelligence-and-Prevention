import React, { useEffect, useState } from "react";
import { api } from "../services/api";

export default function PriorAuth() {
  const [policies, setPolicies] = useState([]);
  const [selectedPolicy, setSelectedPolicy] = useState("");
  const [serviceName, setServiceName] = useState("");
  const [serviceCode, setServiceCode] = useState("");
  const [diagnosisCode, setDiagnosisCode] = useState("");
  const [checklist, setChecklist] = useState(null);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState([]);

  useEffect(() => {
    api.listPolicies().then((p) => {
      setPolicies(p);
      if (p.length > 0) setSelectedPolicy(p[0].document_id);
    });
  }, []);

  const handleGenerate = async () => {
    if (!serviceName.trim() || !selectedPolicy) return;
    setLoading(true);
    setChecklist(null);
    try {
      const r = await api.authChecklist(
        serviceName,
        serviceCode,
        selectedPolicy,
        diagnosisCode
      );
      setChecklist(r);
      setItems(r.items.map((it) => ({ ...it })));
    } catch (e) {
      setChecklist({ error: e.message });
    } finally {
      setLoading(false);
    }
  };

  const toggleItem = (idx) => {
    setItems((prev) =>
      prev.map((it, i) =>
        i === idx ? { ...it, completed: !it.completed } : it
      )
    );
  };

  const completedCount = items.filter((i) => i.completed).length;
  const requiredCount = items.filter((i) => i.required).length;
  const requiredDone = items.filter((i) => i.required && i.completed).length;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Prior Authorization Preparation</h2>

      <div className="bg-white rounded-lg shadow p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Policy
            </label>
            <select
              value={selectedPolicy}
              onChange={(e) => setSelectedPolicy(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm"
            >
              {policies.map((p) => (
                <option key={p.document_id} value={p.document_id}>
                  {p.filename}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Service / Procedure
            </label>
            <input
              value={serviceName}
              onChange={(e) => setServiceName(e.target.value)}
              placeholder="e.g. Knee MRI"
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              CPT / HCPCS Code (optional)
            </label>
            <input
              value={serviceCode}
              onChange={(e) => setServiceCode(e.target.value)}
              placeholder="e.g. 73721"
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Diagnosis Code (optional)
            </label>
            <input
              value={diagnosisCode}
              onChange={(e) => setDiagnosisCode(e.target.value)}
              placeholder="e.g. M17.11"
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
        </div>
        <button
          onClick={handleGenerate}
          disabled={loading || !serviceName.trim()}
          className="bg-blue-600 text-white px-5 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Generating..." : "Generate Checklist"}
        </button>
      </div>

      {checklist?.error && (
        <div className="bg-red-50 text-red-700 p-4 rounded">
          {checklist.error}
        </div>
      )}

      {checklist && !checklist.error && (
        <div className="bg-white rounded-lg shadow p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold">
              Authorization Checklist: {checklist.service_name}
            </h3>
            <div className="text-sm text-gray-500">
              {completedCount}/{items.length} items ·{" "}
              {requiredDone}/{requiredCount} required
            </div>
          </div>

          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all"
              style={{
                width: `${requiredCount ? (requiredDone / requiredCount) * 100 : 0}%`,
              }}
            />
          </div>

          <div className="space-y-2">
            {items.map((item, i) => (
              <div
                key={item.item_id}
                className={`flex items-start gap-3 p-3 rounded border ${
                  item.completed
                    ? "bg-green-50 border-green-200"
                    : "bg-white border-gray-200"
                }`}
              >
                <input
                  type="checkbox"
                  checked={item.completed}
                  onChange={() => toggleItem(i)}
                  className="mt-1"
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">
                      {item.description}
                    </span>
                    {item.required && (
                      <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded">
                        Required
                      </span>
                    )}
                    <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded capitalize">
                      {item.category}
                    </span>
                    <span className="text-xs text-gray-400">
                      Source: {item.source}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {checklist.citations?.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-gray-600 mb-2">
                Policy References
              </h4>
              {checklist.citations.map((c, i) => (
                <div
                  key={i}
                  className="bg-blue-50 border border-blue-200 rounded p-2 text-xs mb-2"
                >
                  <span className="font-semibold text-blue-700">
                    Page {c.page_number || "?"} — {c.section || "General"}
                  </span>
                  <p className="text-gray-600 mt-1 italic">"{c.excerpt}"</p>
                </div>
              ))}
            </div>
          )}

          <div className="bg-amber-50 border border-amber-200 rounded p-3 text-sm">
            <strong>Important:</strong> This checklist is generated from policy
            language analysis and may not be complete. Always verify
            authorization requirements directly with the payer before
            submitting.
          </div>
        </div>
      )}
    </div>
  );
}
