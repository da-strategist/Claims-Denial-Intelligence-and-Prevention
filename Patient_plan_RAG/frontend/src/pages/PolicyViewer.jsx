import React, { useEffect, useState, useRef } from "react";
import { api } from "../services/api";
import { useHashPath, navigate } from "../utils/route";
import { useAuth } from "../auth/AuthContext";
import { isHospital } from "../hooks/usePolicyOptions";

function Badge({ children, title }) {
  return (
    <span className="ml-2 bg-gray-100 text-gray-600 px-2 py-0.5 rounded text-xs" title={title}>
      {children}
    </span>
  );
}

/** Who a document belongs to, from this user's point of view. */
function OwnershipBadge({ doc, user }) {
  if (!doc.owner && !doc.org_id)
    return <Badge title="Synthetic example policy, visible to everyone">Sample</Badge>;
  if (doc.owner === user?.username)
    return <Badge title="Only you, and providers you share it with, can see it">Yours</Badge>;
  if (doc.owner) return <Badge title="A patient shared this with your organisation">Shared by {doc.owner}</Badge>;
  return <Badge title="Uploaded by your organisation for a patient">Patient record</Badge>;
}

const docName = (d) => d.display_name || d.plan_name || d.filename;

/** Whether this user may rename/delete the document (the server re-checks). */
function canManage(doc, user) {
  if (user?.role === "individual") return doc.owner === user.username;
  if (isHospital(user)) return Boolean(doc.org_id) && doc.org_id === user.org_id;
  if (user?.role === "platform_admin") return !doc.owner && !doc.org_id;
  return false;
}

/** Rename or delete a document. */
function ManagePanel({ doc, onRenamed }) {
  const [name, setName] = useState(doc.display_name || "");
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");

  const run = async (fn) => {
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e.message.replace(/^\d+: /, ""));
    }
  };

  return (
    <div className="text-sm mb-4 space-y-2">
      {editing ? (
        <form onSubmit={(e) => {
          e.preventDefault();
          run(async () => {
            onRenamed(await api.renamePolicy(doc.document_id, name.trim()));
            setEditing(false);
          });
        }} className="flex gap-2 items-center">
          <input aria-label="Policy name" maxLength={120} value={name} placeholder={doc.plan_name || doc.filename}
                 onChange={(e) => setName(e.target.value)} className="border rounded px-2 py-1" />
          <button type="submit" className="text-blue-700 hover:underline">Save</button>
          <button type="button" onClick={() => setEditing(false)} className="text-gray-500 hover:underline">Cancel</button>
        </form>
      ) : confirming ? (
        <div className="flex gap-3 items-center">
          <span>Delete this policy{doc.owner ? " and stop sharing it with every provider" : ""}? This can't be undone.</span>
          <button onClick={() => run(async () => {
            await api.deletePolicy(doc.document_id);
            navigate("/policies");
          })} className="bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700">Delete</button>
          <button onClick={() => setConfirming(false)} className="text-gray-500 hover:underline">Cancel</button>
        </div>
      ) : (
        <div className="flex gap-4">
          <button onClick={() => setEditing(true)} className="text-blue-700 hover:underline">Rename</button>
          <button onClick={() => setConfirming(true)} className="text-red-700 hover:underline">Delete</button>
        </div>
      )}
      {error && <p role="alert" className="text-red-600">{error}</p>}
    </div>
  );
}

/** Individuals: share one of their own documents with a provider, or stop. */
function SharePanel({ documentId }) {
  const [hospitals, setHospitals] = useState([]);
  const [shares, setShares] = useState([]);
  const [choice, setChoice] = useState("");
  const [error, setError] = useState("");

  const load = () =>
    Promise.all([api.hospitalDirectory(), api.myShares()])
      .then(([h, s]) => {
        setHospitals(h);
        setShares(s.filter((x) => x.document_id === documentId));
      })
      .catch((e) => setError(e.message.replace(/^\d+: /, "")));
  useEffect(() => { load(); }, [documentId]);

  const act = async (fn) => {
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e.message.replace(/^\d+: /, ""));
    }
  };

  const sharedWith = new Set(shares.map((s) => s.org_id));
  const available = hospitals.filter((h) => !sharedWith.has(h.org_id));

  return (
    <div className="border rounded p-4 mb-4 text-sm">
      <h4 className="font-semibold mb-1">Share with a provider</h4>
      <p className="text-xs text-gray-500 mb-3">
        A provider you share with can read this policy and ask questions about it, until you
        stop sharing.
      </p>
      {shares.length > 0 && (
        <ul className="mb-3 space-y-1">
          {shares.map((s) => (
            <li key={s.share_id}>
              Shared with <strong>{s.org_name}</strong>{" "}
              <button onClick={() => act(() => api.unshare(s.share_id))} className="text-red-700 hover:underline ml-2">
                Stop sharing
              </button>
            </li>
          ))}
        </ul>
      )}
      {available.length > 0 ? (
        <div className="flex gap-2">
          <select aria-label="Provider" value={choice} onChange={(e) => setChoice(e.target.value)}
                  className="border rounded px-2 py-1">
            <option value="">Choose a provider…</option>
            {available.map((h) => (
              <option key={h.org_id} value={h.org_id}>{h.name}{h.category_label ? ` (${h.category_label})` : ""}{h.city ? ` — ${h.city}` : ""}</option>
            ))}
          </select>
          <button disabled={!choice} onClick={() => act(async () => {
            await api.share(documentId, choice);
            setChoice("");
          })} className="border px-3 py-1 rounded hover:bg-gray-50 disabled:opacity-50">
            Share
          </button>
        </div>
      ) : (
        hospitals.length === 0 && <p className="text-xs text-gray-500">No providers are on the platform yet.</p>
      )}
      {error && <p role="alert" className="text-red-600 mt-2">{error}</p>}
    </div>
  );
}

function UploadPanel({ onUploaded }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "platform_admin";
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
      setMsg(`Error: ${e.message.replace(/^\d+: /, "")}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-5 mb-6">
      <h3 className="font-semibold mb-1">
        {isAdmin ? "Upload a sample policy (PDF)" : "Upload your policy document (PDF)"}
      </h3>
      <p className="text-xs text-gray-500 mb-3">
        {isAdmin
          ? "Samples are synthetic example policies that every user can see. Never upload real member documents here."
          : "Only you will be able to see documents you upload, unless you share them with a provider."}
      </p>
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
  const { user } = useAuth();
  const [policy, setPolicy] = useState(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("summary");

  useEffect(() => {
    setError("");
    api.getPolicy(documentId).then(setPolicy).catch((e) => setError(e.message));
  }, [documentId]);

  if (error)
    return (
      <div>
        <p className="text-red-600 text-sm mb-2">Couldn't load this policy: {error}</p>
        <button onClick={() => navigate("/policies")} className="text-blue-600 text-sm hover:underline">
          ← Back to policies
        </button>
      </div>
    );
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
        <h3 className="text-xl font-bold mb-1">
          {docName(policy)}
          <OwnershipBadge doc={policy} user={user} />
        </h3>
        <p className="text-sm text-gray-500 mb-4">
          {policy.page_count} pages · {policy.chunk_count} chunks ·{" "}
          <span className="capitalize">{policy.status}</span>
        </p>
        {canManage(policy, user) && <ManagePanel doc={policy} onRenamed={setPolicy} />}
        {policy.owner && policy.owner === user?.username && <SharePanel documentId={documentId} />}
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
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    setError("");
    api.getPolicyChunks(documentId, page).then(setData).catch((e) => setError(e.message));
  }, [documentId, page]);

  if (error) return <p className="text-red-600 text-sm">Couldn't load chunks: {error}</p>;
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

/** Platform admin: is each sample searchable, current and complete? */
function SampleHealth({ onChanged }) {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState("");
  const load = () => api.sampleHealth().then(setRows).catch((e) => setError(e.message.replace(/^\d+: /, "")));
  useEffect(() => { load(); }, []);

  const reprocess = async (id) => {
    setBusy(id);
    setError("");
    try {
      await api.reprocessSample(id);
      await load();
      onChanged();
    } catch (e) {
      setError(e.message.replace(/^\d+: /, ""));
    } finally {
      setBusy(null);
    }
  };

  if (rows.length === 0 && !error) return null;
  return (
    <section className="bg-white rounded-lg shadow mb-4">
      <h3 className="font-semibold p-4 border-b">Sample health</h3>
      {error && <p role="alert" className="px-4 pt-3 text-sm text-red-600">{error}</p>}
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-gray-500">
            <th className="p-3">Sample</th><th>Pages</th><th>Chunks</th><th>Chunker</th><th>Plan details found</th><th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.document_id} className="border-b align-top">
              <td className="p-3">
                {r.name}
                <span className={`ml-2 px-2 py-0.5 rounded text-xs ${r.healthy ? "bg-green-100 text-green-800" : "bg-amber-100 text-amber-800"}`}>
                  {r.healthy ? "Healthy" : r.problems.join(", ")}
                </span>
              </td>
              <td>{r.page_count}</td>
              <td>{r.chunk_count}</td>
              <td>v{r.chunker_version}{r.chunker_version < r.current_chunker_version && ` (current v${r.current_chunker_version})`}</td>
              <td className="text-xs">
                {r.metadata_found.length}/{r.metadata_found.length + r.metadata_missing.length}
                {r.metadata_missing.length > 0 && (
                  <span className="block text-gray-500">missing: {r.metadata_missing.join(", ").replaceAll("_", " ")}</span>
                )}
              </td>
              <td className="pr-3">
                <button onClick={() => reprocess(r.document_id)} disabled={busy !== null}
                        aria-label={`Re-process ${r.name}`} className="text-xs text-blue-700 hover:underline disabled:opacity-50">
                  {busy === r.document_id ? "Re-processing..." : "Re-process"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export default function PolicyViewer() {
  const path = useHashPath();
  const { user } = useAuth();
  const [policies, setPolicies] = useState([]);

  const load = () => api.listPolicies().then(setPolicies).catch(() => {});
  useEffect(() => { load(); }, []);

  const match = path.match(/^\/policies\/(.+)$/);
  if (match) return <PolicyDetail documentId={match[1]} />;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">
        {user?.role === "individual" ? "My policies" : user?.role === "platform_admin" ? "Sample policies" : "Policy documents"}
      </h2>
      {isHospital(user) ? (
        <p className="text-sm text-gray-600 mb-4">
          Upload a patient's policy from their page under Patients. Policies patients share with
          your organisation appear here and under Shared with us.
        </p>
      ) : (
        <UploadPanel onUploaded={load} />
      )}
      {user?.role === "platform_admin" && <SampleHealth onChanged={load} />}
      <div className="bg-white rounded-lg shadow">
        {policies.length === 0 ? (
          <p className="p-5 text-gray-500">
            {user?.role === "individual"
              ? "Upload your insurance policy above to start asking questions about it."
              : "No policy documents yet."}
          </p>
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
                  <td className="p-3 font-medium">
                    {docName(p)}
                    <OwnershipBadge doc={p} user={user} />
                  </td>
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
