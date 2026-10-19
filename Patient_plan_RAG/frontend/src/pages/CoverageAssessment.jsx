import React, { useEffect, useState } from "react";
import { api } from "../services/api";

const CLASSIFICATION_STYLES = {
  coverage_indicated: { bg: "bg-green-100", text: "text-green-800", label: "Coverage Indicated" },
  conditional_coverage: { bg: "bg-yellow-100", text: "text-yellow-800", label: "Conditional Coverage" },
  exclusion_identified: { bg: "bg-red-100", text: "text-red-800", label: "Exclusion Identified" },
  insufficient_information: { bg: "bg-gray-100", text: "text-gray-800", label: "Insufficient Information" },
  confirmation_required: { bg: "bg-blue-100", text: "text-blue-800", label: "Confirmation Required" },
};

export default function CoverageAssessment() {
  const [policies, setPolicies] = useState([]);
  const [selectedPolicy, setSelectedPolicy] = useState("");
  const [serviceName, setServiceName] = useState("");
  const [serviceCode, setServiceCode] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.listPolicies().then((p) => {
      setPolicies(p);
      if (p.length > 0) setSelectedPolicy(p[0].document_id);
    });
  }, []);

  const handleCheck = async () => {
    if (!serviceName.trim() || !selectedPolicy) return;
    setLoading(true);
    setResult(null);
    try {
      const r = await api.assessCoverage(serviceName, serviceCode, selectedPolicy);
      setResult(r);
    } catch (e) {
      setResult({ error: e.message });
    } finally {
      setLoading(false);
    }
  };

  const style = result?.classification
    ? CLASSIFICATION_STYLES[result.classification] || CLASSIFICATION_STYLES.insufficient_information
    : null;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Coverage Assessment</h2>

      <div className="bg-white rounded-lg shadow p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
              placeholder="e.g. MRI of knee"
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
        </div>
        <button
          onClick={handleCheck}
          disabled={loading || !serviceName.trim()}
          className="bg-blue-600 text-white px-5 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Analyzing..." : "Check Coverage"}
        </button>
      </div>

      {result?.error && (
        <div className="bg-red-50 text-red-700 p-4 rounded">{result.error}</div>
      )}

      {result && !result.error && (
        <div className="bg-white rounded-lg shadow p-5 space-y-4">
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-bold">{result.service_name}</h3>
            <span className={`px-3 py-1 rounded text-sm font-semibold ${style.bg} ${style.text}`}>
              {style.label}
            </span>
          </div>

          <p className="text-sm text-gray-700">{result.explanation}</p>

          {result.conditions.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-gray-600 mb-1">Conditions</h4>
              {result.conditions.map((c, i) => (
                <p key={i} className="text-sm text-gray-600 ml-4">• {c}</p>
              ))}
            </div>
          )}

          {result.exclusions.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-red-600 mb-1">Exclusions</h4>
              {result.exclusions.map((e, i) => (
                <p key={i} className="text-sm text-red-600 ml-4">• {e}</p>
              ))}
            </div>
          )}

          {result.prior_auth_required !== null && (
            <p className="text-sm">
              <strong>Prior Authorization:</strong>{" "}
              {result.prior_auth_required ? "Required" : "Not required"}
            </p>
          )}

          {result.citations.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-gray-600 mb-2">Policy Evidence</h4>
              {result.citations.map((c, i) => (
                <div key={i} className="bg-blue-50 border border-blue-200 rounded p-2 text-xs mb-2">
                  <span className="font-semibold text-blue-700">
                    [{i + 1}] Page {c.page_number || "?"} — {c.section || "General"}
                  </span>
                  <p className="text-gray-600 mt-1 italic">"{c.excerpt}"</p>
                </div>
              ))}
            </div>
          )}

          {result.recommended_steps.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded p-3 text-sm">
              <strong>Recommended Next Steps:</strong>
              {result.recommended_steps.map((s, i) => (
                <p key={i} className="ml-4">• {s}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
