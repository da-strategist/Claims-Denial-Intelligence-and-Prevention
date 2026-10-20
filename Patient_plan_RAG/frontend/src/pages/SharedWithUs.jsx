import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import { navigate } from "../utils/route";

/** Policies individuals shared with this hospital; file each under a patient. */
export default function SharedWithUs() {
  const [shared, setShared] = useState([]);
  const [patients, setPatients] = useState([]);
  const [error, setError] = useState("");

  const load = () =>
    Promise.all([api.listShared(), api.listPatients()])
      .then(([s, p]) => {
        setShared(s);
        setPatients(p);
      })
      .catch((e) => setError(e.message.replace(/^\d+: /, "")));
  useEffect(() => { load(); }, []);

  const file = async (shareId, patientId) => {
    setError("");
    try {
      await api.fileShared(shareId, patientId);
      load();
    } catch (e) {
      setError(e.message.replace(/^\d+: /, ""));
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">Shared with us</h2>
      <p className="text-sm text-gray-600">
        Policies that patients chose to share with your hospital. File each one under the
        patient's record so it is included when you ask about that patient. A patient can stop
        sharing at any time.
      </p>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      <div className="bg-white rounded-lg shadow">
        {shared.length === 0 ? (
          <p className="p-5 text-sm text-gray-500">Nothing has been shared with your hospital yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="p-3">Policy</th>
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
                  </td>
                  <td>{s.shared_by}</td>
                  <td>
                    <select
                      aria-label={`Patient for ${s.plan_name || s.filename}`}
                      value={s.patient_id || ""}
                      onChange={(e) => file(s.share_id, e.target.value)}
                      className="border rounded px-2 py-1 text-sm"
                    >
                      <option value="">Not filed</option>
                      {patients.map((p) => (
                        <option key={p.patient_id} value={p.patient_id}>
                          {p.name}{p.reference ? ` (${p.reference})` : ""}
                        </option>
                      ))}
                    </select>
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
