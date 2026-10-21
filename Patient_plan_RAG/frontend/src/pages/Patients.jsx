import React, { useEffect, useRef, useState } from "react";
import { api } from "../services/api";
import { navigate, useHashPath } from "../utils/route";

const clean = (msg) => msg.replace(/^\d+: /, "");
const fmt = (iso) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString() : "—");
const docName = (d) => d.display_name || d.plan_name || d.filename;

const STATUS = {
  active: "bg-green-100 text-green-800",
  ended: "bg-amber-100 text-amber-800",
  upcoming: "bg-blue-100 text-blue-800",
  unknown: "bg-gray-100 text-gray-600",
};

function PatientForm({ initial, submitLabel, onSubmit, onCancel }) {
  const [form, setForm] = useState(initial);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await onSubmit({ ...form, name: form.name.trim() });
    } catch (err) {
      setError(clean(err.message));
    }
  };

  const field = (label, key, props = {}) => (
    <label className="text-sm">
      <span className="block text-gray-700">{label}</span>
      <input value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })}
             className="border rounded px-3 py-1.5" {...props} />
    </label>
  );

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="flex flex-wrap gap-3 items-end">
        {field("Name", "name", { required: true, maxLength: 200 })}
        {field("Hospital number (MRN)", "reference", { maxLength: 50 })}
        {field("Date of birth", "date_of_birth", { type: "date" })}
        <button type="submit" className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">
          {submitLabel}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} className="text-sm text-gray-500 hover:underline">Cancel</button>
        )}
      </div>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
    </form>
  );
}

function Insurance({ documents, onOpen }) {
  if (documents.length === 0)
    return <p className="text-sm text-gray-500">No policy documents yet. Upload one below.</p>;
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b text-left text-gray-500">
          <th className="py-2">Insurer</th>
          <th>Plan</th>
          <th>Plan ID</th>
          <th>Coverage</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {documents.map((d) => (
          <tr key={d.document_id} className="border-b">
            <td className="py-2">{d.insurer_name || "—"}</td>
            <td>
              <button onClick={() => onOpen(d.document_id)} className="text-blue-700 hover:underline">{docName(d)}</button>
              {d.shared_by && <span className="text-gray-500 text-xs"> · shared by {d.shared_by}</span>}
            </td>
            <td>{d.plan_id || "—"}</td>
            <td>{d.effective_date || d.expiration_date ? `${fmt(d.effective_date)} – ${fmt(d.expiration_date)}` : "—"}</td>
            <td>
              <span className={`px-2 py-0.5 rounded text-xs capitalize ${STATUS[d.coverage_status] || STATUS.unknown}`}>
                {d.coverage_status === "unknown" ? "Dates not stated" : d.coverage_status}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SavedChecklists({ patientId }) {
  const [lists, setLists] = useState([]);
  const [error, setError] = useState("");
  const load = () => api.listChecklists(patientId).then(setLists).catch((e) => setError(clean(e.message)));
  useEffect(() => { load(); }, [patientId]);

  const toggle = async (list, idx) => {
    const items = list.items.map((it, i) => (i === idx ? { ...it, completed: !it.completed } : it));
    setLists((prev) => prev.map((l) => (l.checklist_id === list.checklist_id ? { ...l, items } : l)));
    try {
      await api.updateChecklist(patientId, list.checklist_id, items);
    } catch (e) {
      setError(clean(e.message));
      load();
    }
  };

  if (lists.length === 0) return <p className="text-sm text-gray-500">No saved checklists yet.</p>;
  return (
    <div className="space-y-4">
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      {lists.map((l) => {
        const done = l.items.filter((i) => i.completed).length;
        return (
          <div key={l.checklist_id} className="border rounded p-3 text-sm">
            <div className="flex justify-between mb-2">
              <strong>{l.service_name}{l.service_code && ` (${l.service_code})`}</strong>
              <span className="text-gray-500">
                {done}/{l.items.length} done · saved by {l.created_by} ·{" "}
                <button onClick={async () => { await api.deleteChecklist(patientId, l.checklist_id); load(); }}
                        className="text-red-700 hover:underline">Delete</button>
              </span>
            </div>
            <ul className="space-y-1">
              {l.items.map((it, i) => (
                <li key={it.item_id + i}>
                  <label className="flex gap-2 items-start">
                    <input type="checkbox" checked={Boolean(it.completed)} onChange={() => toggle(l, i)} />
                    <span className={it.completed ? "line-through text-gray-400" : ""}>
                      {it.description}{it.required ? "" : " (if applicable)"}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

function PatientDetail({ patientId }) {
  const [patient, setPatient] = useState(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [uploading, setUploading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const fileRef = useRef();

  const load = () => api.getPatient(patientId).then(setPatient).catch((e) => setError(clean(e.message)));
  useEffect(() => { load(); }, [patientId]);

  const upload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setMsg("");
    try {
      await api.uploadPolicy(file, patientId);
      setMsg("Policy uploaded.");
      if (fileRef.current) fileRef.current.value = "";
      load();
    } catch (e) {
      setMsg(`Error: ${clean(e.message)}`);
    } finally {
      setUploading(false);
    }
  };

  const act = async (fn) => {
    setMsg("");
    try {
      await fn();
    } catch (e) {
      setMsg(`Error: ${clean(e.message)}`);
    }
  };

  if (error) return <p role="alert" className="text-red-600 text-sm">Couldn't load this patient: {error}</p>;
  if (!patient) return <p className="text-gray-500">Loading...</p>;
  const hasDocs = patient.documents.length > 0;

  return (
    <div className="space-y-4">
      <button onClick={() => navigate("/patients")} className="text-blue-600 text-sm hover:underline">
        ← All patients
      </button>
      <div className="bg-white rounded-lg shadow p-5 space-y-3">
        {editing ? (
          <PatientForm
            initial={{ name: patient.name, reference: patient.reference, date_of_birth: patient.date_of_birth }}
            submitLabel="Save"
            onSubmit={async (changes) => { setPatient(await api.updatePatient(patientId, changes)); setEditing(false); }}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <div>
            <h2 className="text-xl font-bold">
              {patient.name}
              {patient.archived && <span className="ml-2 bg-gray-100 text-gray-600 px-2 py-0.5 rounded text-xs">Archived</span>}
            </h2>
            <p className="text-sm text-gray-500">
              {patient.reference && <>MRN {patient.reference} · </>}
              {patient.date_of_birth && <>Born {patient.date_of_birth} · </>}
              {patient.documents.length} policy document(s)
            </p>
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          <button onClick={() => navigate(`/chat?patient=${patientId}`)} disabled={!hasDocs}
                  className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50">
            Ask about coverage
          </button>
          <button onClick={() => navigate(`/coverage?patient=${patientId}`)} disabled={!hasDocs}
                  className="border px-4 py-1.5 rounded text-sm hover:bg-gray-50 disabled:opacity-50">
            Check coverage for a service
          </button>
          <button onClick={() => navigate(`/auth?patient=${patientId}`)} disabled={!hasDocs}
                  className="border px-4 py-1.5 rounded text-sm hover:bg-gray-50 disabled:opacity-50">
            Prior auth checklist
          </button>
        </div>
        <div className="flex flex-wrap gap-4 text-xs">
          {!editing && <button onClick={() => setEditing(true)} className="text-blue-700 hover:underline">Edit details</button>}
          <button onClick={() => act(async () => setPatient(await api.updatePatient(patientId, { archived: !patient.archived })))}
                  className="text-blue-700 hover:underline">
            {patient.archived ? "Restore" : "Archive"}
          </button>
          {confirmDelete ? (
            <span className="flex gap-2 items-center">
              Delete this patient and the policies your hospital uploaded for them? Policies the
              patient shared stay theirs.
              <button onClick={() => act(async () => { await api.deletePatient(patientId); navigate("/patients"); })}
                      className="bg-red-600 text-white px-2 py-0.5 rounded">Delete</button>
              <button onClick={() => setConfirmDelete(false)} className="text-gray-500 hover:underline">Cancel</button>
            </span>
          ) : (
            <button onClick={() => setConfirmDelete(true)} className="text-red-700 hover:underline">Delete patient</button>
          )}
        </div>
        {msg && <p className="text-sm text-gray-600">{msg}</p>}
      </div>

      <div className="bg-white rounded-lg shadow p-5">
        <h3 className="font-semibold mb-2">Insurance</h3>
        <Insurance documents={patient.documents} onOpen={(id) => navigate(`/policies/${id}`)} />
        <div className="flex items-center gap-3 mt-4">
          <input ref={fileRef} type="file" accept=".pdf" className="text-sm" aria-label="Policy PDF" />
          <button onClick={upload} disabled={uploading}
                  className="border px-4 py-1.5 rounded text-sm hover:bg-gray-50 disabled:opacity-50">
            {uploading ? "Processing..." : "Upload policy for this patient"}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-5">
        <h3 className="font-semibold mb-2">Prior authorization checklists</h3>
        <SavedChecklists patientId={patientId} />
      </div>
    </div>
  );
}

export default function Patients() {
  const path = useHashPath();
  const [patients, setPatients] = useState([]);
  const [filter, setFilter] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [error, setError] = useState("");

  const load = () => api.listPatients(showArchived).then(setPatients).catch((e) => setError(clean(e.message)));
  useEffect(() => { load(); }, [showArchived]);

  const match = path.match(/^\/patients\/([A-Za-z0-9_-]+)$/);
  if (match) return <PatientDetail patientId={match[1]} />;

  const q = filter.trim().toLowerCase();
  const shown = patients.filter((p) => !q || p.name.toLowerCase().includes(q) || p.reference.toLowerCase().includes(q));

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Patients</h2>
      <section className="bg-white rounded-lg shadow p-5">
        <h3 className="font-semibold mb-3">Add a patient</h3>
        <PatientForm initial={{ name: "", reference: "", date_of_birth: "" }} submitLabel="Add patient"
                     onSubmit={async (p) => { const created = await api.createPatient(p); navigate(`/patients/${created.patient_id}`); }} />
      </section>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      <div className="bg-white rounded-lg shadow">
        <div className="p-3 border-b flex items-center gap-4">
          <input placeholder="Search by name or MRN" value={filter} onChange={(e) => setFilter(e.target.value)}
                 className="border rounded px-3 py-1.5 text-sm w-64" />
          <label className="text-sm flex items-center gap-1">
            <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
            Show archived
          </label>
        </div>
        {shown.length === 0 ? (
          <p className="p-5 text-gray-500 text-sm">
            {patients.length === 0 ? "No patients yet. Add one above." : "No patients match."}
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="p-3">Name</th>
                <th>MRN</th>
                <th>Date of birth</th>
                <th>Insurance</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((p) => (
                <tr key={p.patient_id} className="border-b hover:bg-gray-50 cursor-pointer"
                    onClick={() => navigate(`/patients/${p.patient_id}`)}>
                  <td className="p-3 font-medium">
                    {p.name}
                    {p.archived && <span className="ml-2 text-xs text-gray-500">(archived)</span>}
                  </td>
                  <td>{p.reference || "—"}</td>
                  <td>{p.date_of_birth || "—"}</td>
                  <td>
                    {p.documents.length === 0 ? "—" : p.documents.map((d) => (
                      <span key={d.document_id} className={`mr-1 px-2 py-0.5 rounded text-xs ${STATUS[d.coverage_status] || STATUS.unknown}`}>
                        {d.insurer_name || docName(d)}
                      </span>
                    ))}
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
