import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import { navigate } from "../utils/route";

const fmt = (iso) => (iso ? new Date(iso).toLocaleDateString() : "");
const NewBadge = () => <span className="ml-2 bg-blue-100 text-blue-800 px-2 py-0.5 rounded text-xs">New</span>;

function PatientSelect({ label, value, patients, onChange }) {
  return (
    <select aria-label={label} value={value || ""} onChange={(e) => onChange(e.target.value)}
            className="border rounded px-2 py-1 text-sm">
      <option value="">Not filed</option>
      {patients.map((p) => (
        <option key={p.patient_id} value={p.patient_id}>
          {p.name}{p.reference ? ` (${p.reference})` : ""}
        </option>
      ))}
    </select>
  );
}

/** People who added this provider, and policies they shared; file each under a patient. */
export default function SharedWithUs() {
  const [shared, setShared] = useState([]);
  const [connections, setConnections] = useState([]);
  const [patients, setPatients] = useState([]);
  const [error, setError] = useState("");

  const load = () =>
    Promise.all([api.listShared(), api.listConnections(), api.listPatients()])
      .then(([s, c, p]) => {
        setShared(s);
        setConnections(c);
        setPatients(p);
      })
      .catch((e) => setError(e.message.replace(/^\d+: /, "")));
  useEffect(() => { load(); }, []);

  const act = async (fn) => {
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e.message.replace(/^\d+: /, ""));
    }
  };
  const file = (shareId, patientId) => act(() => api.fileShared(shareId, patientId));
  const createRecord = (c) => act(async () => {
    const p = await api.createPatient({ name: c.name || c.email });
    await api.fileConnection(c.connection_id, p.patient_id);
  });

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">Shared with us</h2>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}

      <section className="bg-white rounded-lg shadow">
        <div className="p-4 border-b">
          <h3 className="font-semibold">Patients who added you</h3>
          <p className="text-sm text-gray-600 mt-1">
            People who added your organisation to their providers. You see their name and email
            only; their policies appear below if they choose to share them. Attach each person to
            their patient record: policies they share then file themselves.
          </p>
        </div>
        {connections.length === 0 ? (
          <p className="p-4 text-sm text-gray-500">No one has added your organisation yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="p-3">Person</th>
                <th>Added you</th>
                <th>Policies shared</th>
                <th>Patient record</th>
              </tr>
            </thead>
            <tbody>
              {connections.map((c) => (
                <tr key={c.connection_id} className="border-b">
                  <td className="p-3">
                    {c.name || c.email}
                    {c.is_new && <NewBadge />}
                    {c.name && <span className="block text-xs text-gray-500">{c.email}</span>}
                  </td>
                  <td>{fmt(c.connected_at)}</td>
                  <td>{c.shared_count}</td>
                  <td className="py-2 pr-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <PatientSelect label={`Patient record for ${c.name || c.email}`} value={c.patient_id}
                                     patients={patients} onChange={(id) => act(() => api.fileConnection(c.connection_id, id))} />
                      {c.patient_id ? (
                        <button onClick={() => navigate(`/patients/${c.patient_id}`)} className="text-blue-700 hover:underline text-xs">
                          Open record
                        </button>
                      ) : (
                        <button onClick={() => createRecord(c)} className="text-blue-700 hover:underline text-xs">
                          Create patient record
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b">
          <h3 className="font-semibold">Shared policies</h3>
          <p className="text-sm text-gray-600 mt-1">
            Policies that patients chose to share with your organisation. File each one under the
            patient's record so it is included when you ask about that patient. A patient can stop
            sharing at any time.
          </p>
        </div>
        {shared.length === 0 ? (
          <p className="p-5 text-sm text-gray-500">Nothing has been shared with your organisation yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="p-3">Policy</th>
                <th>Insurer</th>
                <th>Shared by</th>
                <th>Filed under patient</th>
              </tr>
            </thead>
            <tbody>
              {shared.map((s) => (
                <tr key={s.share_id} className="border-b">
                  <td className="p-3">
                    <button onClick={() => navigate(`/policies/${s.document_id}`)} className="text-blue-700 hover:underline">
                      {s.plan_name || s.filename}
                    </button>
                    {s.is_new && <NewBadge />}
                  </td>
                  <td>{s.insurer_name || "—"}</td>
                  <td>
                    {s.shared_by_name || s.shared_by}
                    {s.shared_by_name && <span className="block text-xs text-gray-500">{s.shared_by}</span>}
                  </td>
                  <td>
                    <PatientSelect label={`Patient for ${s.plan_name || s.filename}`} value={s.patient_id}
                                   patients={patients} onChange={(id) => file(s.share_id, id)} />
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
