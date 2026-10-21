import React, { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { isHospital, usePolicyOptions } from "./usePolicyOptions";

/** Patient preselected by a link like #/coverage?patient=<id> */
export function patientFromHash() {
  const query = window.location.hash.split("?")[1] || "";
  return new URLSearchParams(query).get("patient") || "";
}

/**
 * Document picker for Coverage Check and Prior Auth. Hospital staff choose a
 * patient first, then one of that patient's documents; others choose from
 * their documents. Returns the selection and the picker to render.
 */
export function usePolicyPicker() {
  const { user } = useAuth();
  const hospital = isHospital(user);
  const { options, patients, error } = usePolicyOptions();
  const [patientId, setPatientId] = useState(patientFromHash);
  const [policyId, setPolicyId] = useState("");

  const patient = patients.find((p) => p.patient_id === patientId);
  const choices = hospital
    ? options.filter((o) => patient?.documents.some((d) => d.document_id === o.id))
    : options;

  // default to the first available document whenever the choices change
  useEffect(() => {
    if (!choices.some((o) => o.id === policyId)) setPolicyId(choices[0]?.id || "");
  }, [choices.map((o) => o.id).join(","), policyId]);

  const picker = (
    <div className="space-y-3">
      {hospital && (
        <label className="block">
          <span className="block text-sm font-medium text-gray-700 mb-1">Patient</span>
          <select aria-label="Patient" value={patientId} onChange={(e) => setPatientId(e.target.value)}
                  className="w-full border rounded px-3 py-2 text-sm">
            <option value="">Choose a patient…</option>
            {patients.map((p) => (
              <option key={p.patient_id} value={p.patient_id}>
                {p.name}{p.reference ? ` (${p.reference})` : ""}
              </option>
            ))}
          </select>
        </label>
      )}
      <label className="block">
        <span className="block text-sm font-medium text-gray-700 mb-1">Policy</span>
        <select aria-label="Policy" value={policyId} onChange={(e) => setPolicyId(e.target.value)}
                disabled={hospital && !patientId}
                className="w-full border rounded px-3 py-2 text-sm">
          {choices.length === 0 && (
            <option value="">{!hospital ? "No policies" : patientId ? "No policies for this patient" : "Choose a patient first"}</option>
          )}
          {choices.map((o) => (
            <option key={o.id} value={o.id}>{o.label}</option>
          ))}
        </select>
      </label>
      {error && <p className="text-xs text-red-600">Couldn't load policies: {error}</p>}
    </div>
  );

  return { policyId, patientId: hospital ? patientId : "", patient, picker, hospital };
}
