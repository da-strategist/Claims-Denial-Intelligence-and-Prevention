import { useCallback, useEffect, useState } from "react";
import { api } from "../services/api";
import { useAuth } from "../auth/AuthContext";

export const isHospital = (user) =>
  user?.role === "hospital_staff" || user?.role === "hospital_admin";

const isSample = (p) => !p.owner && !p.org_id;
const name = (p) => p.plan_name || p.filename;

/**
 * The documents this user may pick, labelled for their role and ordered:
 * their own (or their patients') first, then shared with them, then samples.
 * Hospital users also get the patient list.
 */
export function usePolicyOptions() {
  const { user } = useAuth();
  const [options, setOptions] = useState([]);
  const [patients, setPatients] = useState([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [policies, pts] = await Promise.all([
        api.listPolicies(),
        isHospital(user) ? api.listPatients() : Promise.resolve([]),
      ]);
      const patientName = Object.fromEntries(pts.map((p) => [p.patient_id, p.name]));
      const labelled = policies.map((p) => {
        if (isSample(p)) return { id: p.document_id, label: `${name(p)} (sample)`, rank: 2, doc: p };
        if (p.patient_id)
          return { id: p.document_id, label: `${patientName[p.patient_id] || "Patient"} — ${name(p)}`,
                   rank: 0, doc: p };
        if (isHospital(user))
          return { id: p.document_id, label: `${name(p)} (shared by ${p.owner})`, rank: 1, doc: p };
        return { id: p.document_id, label: name(p), rank: 0, doc: p };
      });
      labelled.sort((a, b) => a.rank - b.rank || a.label.localeCompare(b.label));
      setOptions(labelled);
      setPatients(pts);
    } catch (e) {
      setError(e.message);
    }
  }, [user]);

  useEffect(() => { load(); }, [load]);

  return { options, patients, error, reload: load };
}
