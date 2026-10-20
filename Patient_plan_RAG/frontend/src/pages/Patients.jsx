import React, { useEffect, useRef, useState } from "react";
import { api } from "../services/api";
import { navigate, useHashPath } from "../utils/route";

const clean = (msg) => msg.replace(/^\d+: /, "");

function NewPatientForm({ onCreated }) {
  const [form, setForm] = useState({ name: "", reference: "", date_of_birth: "" });
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const p = await api.createPatient({ ...form, name: form.name.trim() });
      setForm({ name: "", reference: "", date_of_birth: "" });
      onCreated(p);
    } catch (err) {
      setError(clean(err.message));
    }
  };

  const field = (label, key, props = {}) => (
    <label className="text-sm">
      <span className="block text-gray-700">{label}</span>
      <input
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        className="border rounded px-3 py-1.5"
        {...props}
      />
    </label>
  );

  return (
    <form onSubmit={submit} className="bg-white rounded-lg shadow p-5 space-y-3">
      <h3 className="font-semibold">Add a patient</h3>
      <div className="flex flex-wrap gap-3 items-end">
        {field("Name", "name", { required: true, maxLength: 200 })}
        {field("Hospital number (MRN)", "reference", { maxLength: 50 })}
        {field("Date of birth", "date_of_birth", { type: "date" })}
        <button type="submit" className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">
          Add patient
        </button>
      </div>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
    </form>
  );
}

function PatientDetail({ patientId }) {
  const [patient, setPatient] = useState(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [uploading, setUploading] = useState(false);
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

  if (error) return <p role="alert" className="text-red-600 text-sm">Couldn't load this patient: {error}</p>;
  if (!patient) return <p className="text-gray-500">Loading...</p>;

  return (
    <div className="space-y-4">
      <button onClick={() => navigate("/patients")} className="text-blue-600 text-sm hover:underline">
        ← All patients
      </button>
      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-xl font-bold">{patient.name}</h2>
        <p className="text-sm text-gray-500">
          {patient.reference && <>MRN {patient.reference} · </>}
          {patient.date_of_birth && <>Born {patient.date_of_birth} · </>}
          {patient.documents.length} policy document(s)
        </p>
        <button
          onClick={() => navigate(`/chat?patient=${patient.patient_id}`)}
          disabled={patient.documents.length === 0}
          className="mt-3 bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          Ask about this patient's coverage
        </button>
      </div>

      <div className="bg-white rounded-lg shadow p-5">
        <h3 className="font-semibold mb-2">Policy documents</h3>
        {patient.documents.length === 0 ? (
          <p className="text-sm text-gray-500">No policy documents yet. Upload one below.</p>
        ) : (
          <ul className="text-sm space-y-1 mb-4">
            {patient.documents.map((d) => (
              <li key={d.document_id}>
                <button onClick={() => navigate(`/policies/${d.document_id}`)} className="text-blue-700 hover:underline">
                  {d.plan_name || d.filename}
                </button>
                {d.insurer_name && <span className="text-gray-500"> · {d.insurer_name}</span>}
                {d.shared_by && <span className="text-gray-500"> · shared by {d.shared_by}</span>}
              </li>
            ))}
          </ul>
        )}
        <div className="flex items-center gap-3">
          <input ref={fileRef} type="file" accept=".pdf" className="text-sm" aria-label="Policy PDF" />
          <button
            onClick={upload}
            disabled={uploading}
            className="border px-4 py-1.5 rounded text-sm hover:bg-gray-50 disabled:opacity-50"
          >
            {uploading ? "Processing..." : "Upload policy for this patient"}
          </button>
        </div>
        {msg && <p className="text-sm mt-2 text-gray-600">{msg}</p>}
      </div>
    </div>
  );
}

export default function Patients() {
  const path = useHashPath();
  const [patients, setPatients] = useState([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");

  const load = () => api.listPatients().then(setPatients).catch((e) => setError(clean(e.message)));
  useEffect(() => { load(); }, []);

  const match = path.match(/^\/patients\/([A-Za-z0-9_-]+)$/);
  if (match) return <PatientDetail patientId={match[1]} />;

  const q = filter.trim().toLowerCase();
  const shown = patients.filter((p) => !q || p.name.toLowerCase().includes(q) || p.reference.toLowerCase().includes(q));

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Patients</h2>
      <NewPatientForm onCreated={(p) => navigate(`/patients/${p.patient_id}`)} />
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      <div className="bg-white rounded-lg shadow">
        <div className="p-3 border-b">
          <input
            placeholder="Search by name or MRN"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="border rounded px-3 py-1.5 text-sm w-64"
          />
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
                <th>Policies</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((p) => (
                <tr key={p.patient_id} className="border-b hover:bg-gray-50 cursor-pointer"
                    onClick={() => navigate(`/patients/${p.patient_id}`)}>
                  <td className="p-3 font-medium">{p.name}</td>
                  <td>{p.reference || "—"}</td>
                  <td>{p.date_of_birth || "—"}</td>
                  <td>{p.documents.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
