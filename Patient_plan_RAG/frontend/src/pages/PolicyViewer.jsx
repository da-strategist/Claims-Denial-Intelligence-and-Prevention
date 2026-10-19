import React, { useEffect, useState, useRef } from "react";
import { api } from "../services/api";
import { useHashPath, navigate } from "../utils/route";

function UploadPanel({ onUploaded }) {
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState("");
  const fileRef = useRef();

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setMsg("");
    try {
      const result = await api.uploadPolicy(file);
      setMsg(`Uploaded: ${result.message}`);
      onUploaded?.();
    } catch (e) {
      setMsg(`Error: ${e.message}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-5 mb-6">
      <h3 className="font-semibold mb-3">Upload Policy Document (PDF)</h3>
      <div className="flex items-center gap-3">
        <input
          ref={fileRef}
          type="file"
          accept=".pdf"
          className="text-sm"
        />
        <button
          onClick={handleUpload}
          disabled={uploading}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {uploading ? "Processing..." : "Upload & Process"}
        </button>
      </div>
      {msg && <p className="text-sm mt-2 text-gray-600">{msg}</p>}
    </div>
  );
}

function PolicySummaryView({ documentId }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .getPolicySummary(documentId)
      .then(setSummary)
      .catch(() => setSummary(null))
      .finally(() => setLoading(false));
  }, [documentId]);

  if (loading) return <p className="text-gray-500">Loading summary...</p>;
  if (!summary) return <p className="text-gray-500">No summary available.</p>;

  return (
    <div className="space-y-4">
      {summary.plan_overview && (
        <div>
          <h4 className="font-semibold text-gray-700 mb-1">Plan Overview</h4>
          <p className="text-sm whitespace-pre-line">{summary.plan_overview}</p>
        </div>
      )}
      {summary.deductible?.description && (
        <div>
          <h4 className="font-semibold text-gray-700 mb-1">Deductible</h4>
          <p className="text-sm">{summary.deductible.description}</p>
        </div>
      )}
      {summary.copayments.length > 0 && (
        <div>
          <h4 className="font-semibold text-gray-700 mb-1">Copayments</h4>
          {summary.copayments.map((c, i) => (
            <p key={i} className="text-sm">
              <strong>{c.service}:</strong> {c.amount}
            </p>
          ))}
        </div>
      )}
      {summary.covered_services.length > 0 && (
        <div>
          <h4 className="font-semibold text-gray-700 mb-1">Covered Services</h4>
          {summary.covered_services.map((s, i) => (
            <p key={i} className="text-sm">
              <strong>{s.service}:</strong> {s.description}
            </p>
          ))}
        </div>
      )}
      {summary.excluded_services.length > 0 && (
        <div>
          <h4 className="font-semibold text-gray-700 mb-1">Exclusions</h4>
          {summary.excluded_services.map((s, i) => (
            <p key={i} className="text-sm">
              <strong>{s.service}:</strong> {s.description}
            </p>
          ))}
        </div>
      )}
      {summary.prior_auth_services.length > 0 && (
        <div>
          <h4 className="font-semibold text-gray-700 mb-1">
            Prior Authorization Requirements
          </h4>
          {summary.prior_auth_services.map((s, i) => (
            <p key={i} className="text-sm">
              <strong>{s.service}:</strong> {s.requirement}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function PolicyDetail({ documentId }) {
  const [policy, setPolicy] = useState(null);
  const [tab, setTab] = useState("summary");

  useEffect(() => {
    api.getPolicy(documentId).then(setPolicy).catch(() => {});
  }, [documentId]);

  if (!policy) return <p className="text-gray-500">Loading...</p>;

  return (
    <div>
      <button
        onClick={() => navigate("/policies")}
        className="text-blue-600 text-sm mb-4 hover:underline"
      >
        ← Back to policies
      </button>
      <div className="bg-white rounded-lg shadow p-5">
        <h3 className="text-xl font-bold mb-1">{policy.filename}</h3>
        <p className="text-sm text-gray-500 mb-4">
          {policy.page_count} pages · {policy.chunk_count} chunks ·{" "}
          <span className="capitalize">{policy.status}</span>
        </p>
        <div className="flex gap-2 mb-4 border-b">
          {["summary", "chunks"].map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-2 text-sm capitalize ${
                tab === t
                  ? "border-b-2 border-blue-600 font-semibold"
                  : "text-gray-500"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        {tab === "summary" ? (
          <PolicySummaryView documentId={documentId} />
        ) : (
          <ChunkList documentId={documentId} />
        )}
      </div>
    </div>
  );
}

function ChunkList({ documentId }) {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);

  useEffect(() => {
    api.getPolicyChunks(documentId, page).then(setData).catch(() => {});
  }, [documentId, page]);

  if (!data) return <p className="text-gray-500">Loading chunks...</p>;

  return (
    <div className="space-y-3">
      {data.items.map((c) => (
        <div key={c.chunk_id} className="border rounded p-3 text-sm">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Page {c.page_number || "?"}</span>
            <span>{c.section_heading || "—"}</span>
          </div>
          <p className="whitespace-pre-line">{c.content}</p>
        </div>
      ))}
      <div className="flex justify-between items-center text-sm">
        <span className="text-gray-500">
          Page {data.page} · {data.total} chunks total
        </span>
        <div className="flex gap-2">
          <button
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
            className="px-3 py-1 border rounded disabled:opacity-30"
          >
            Prev
          </button>
          <button
            disabled={page * data.page_size >= data.total}
            onClick={() => setPage(page + 1)}
            className="px-3 py-1 border rounded disabled:opacity-30"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}

export default function PolicyViewer() {
  const path = useHashPath();
  const [policies, setPolicies] = useState([]);

  const load = () => api.listPolicies().then(setPolicies).catch(() => {});
  useEffect(() => { load(); }, []);

  const match = path.match(/^\/policies\/(.+)$/);
  if (match) return <PolicyDetail documentId={match[1]} />;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Policy Documents</h2>
      <UploadPanel onUploaded={load} />
      <div className="bg-white rounded-lg shadow">
        {policies.length === 0 ? (
          <p className="p-5 text-gray-500">No policies loaded yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="p-3">Filename</th>
                <th>Pages</th>
                <th>Chunks</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {policies.map((p) => (
                <tr
                  key={p.document_id}
                  className="border-b hover:bg-gray-50 cursor-pointer"
                  onClick={() => navigate(`/policies/${p.document_id}`)}
                >
                  <td className="p-3 font-medium">{p.filename}</td>
                  <td>{p.page_count}</td>
                  <td>{p.chunk_count}</td>
                  <td>
                    <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs">
                      {p.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
