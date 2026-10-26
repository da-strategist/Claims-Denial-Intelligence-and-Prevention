import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import Staff from "./Staff";

const clean = (msg) => msg.replace(/^\d+: /, "");

function Profile() {
  const [form, setForm] = useState(null);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.getHospitalProfile().then(setForm).catch((e) => setError(clean(e.message)));
  }, []);
  if (error && !form) return <p role="alert" className="text-sm text-red-600">{error}</p>;
  if (!form) return <p className="text-gray-500">Loading...</p>;

  const field = (label, key, props = {}) => (
    <label className="block text-sm">
      <span className="text-gray-700">{label}</span>
      <input value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })}
             className="mt-1 w-full border rounded px-3 py-1.5" {...props} />
    </label>
  );

  return (
    <form onSubmit={async (e) => {
      e.preventDefault();
      setMsg("");
      setError("");
      try {
        const { address, city, phone, contact_email } = form;
        setForm(await api.updateHospitalProfile({ address, city, phone, contact_email }));
        setMsg("Profile saved.");
      } catch (err) {
        setError(clean(err.message));
      }
    }} className="bg-white rounded-lg shadow p-5 space-y-3 max-w-xl">
      <p className="text-sm text-gray-600">
        <strong>{form.name}</strong>. Individuals see these details when choosing which provider
        to share a policy with, so they can tell providers with similar names apart.
      </p>
      {field("Address", "address", { maxLength: 200 })}
      {field("City", "city", { maxLength: 100 })}
      {field("Phone", "phone", { maxLength: 30 })}
      {field("Contact email", "contact_email", { type: "email", maxLength: 254 })}
      <button type="submit" className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">Save</button>
      {msg && <p role="status" className="text-sm text-green-700">{msg}</p>}
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
    </form>
  );
}

function AccessLog() {
  const [rows, setRows] = useState(null);
  const [filter, setFilter] = useState("");
  const [routine, setRoutine] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    api.accessLog(routine).then(setRows).catch((e) => setError(clean(e.message)));
  }, [routine]);
  if (error) return <p role="alert" className="text-sm text-red-600">{error}</p>;
  if (!rows) return <p className="text-gray-500">Loading...</p>;
  const q = filter.trim().toLowerCase();
  const shown = rows.filter((r) => !q || [r.user, r.patient_name, r.label].some((v) => v?.toLowerCase().includes(q)));
  return (
    <div className="bg-white rounded-lg shadow">
      <div className="p-3 border-b flex items-center gap-3">
        <input placeholder="Filter by staff, patient or action" value={filter}
               onChange={(e) => setFilter(e.target.value)} className="border rounded px-3 py-1.5 text-sm w-72" />
        <label className="text-sm flex items-center gap-1">
          <input type="checkbox" checked={routine} onChange={(e) => setRoutine(e.target.checked)} />
          Show page loads
        </label>
        <span className="text-xs text-gray-500">Your staff's activity, newest first. Question text is never recorded.</span>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-gray-500">
            <th className="p-3">When</th>
            <th>Staff</th>
            <th>Action</th>
            <th>Patient</th>
            <th>Result</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((r, i) => (
            <tr key={i} className="border-b">
              <td className="p-3 whitespace-nowrap">{new Date(r.ts).toLocaleString()}</td>
              <td>{r.user}</td>
              <td className={r.routine ? "text-gray-500" : ""}>{r.label}</td>
              <td>{r.patient_name || "—"}</td>
              <td className={r.status >= 400 ? "text-red-700" : ""}>{r.status >= 400 ? `Refused (${r.status})` : "OK"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const TABS = [["staff", "Staff"], ["profile", "Organisation profile"], ["log", "Access log"]];

/** Provider admins: staff, the organisation's public profile, and the access log. */
export default function HospitalAdmin() {
  const [tab, setTab] = useState("staff");
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">Provider admin</h2>
      <div role="tablist" className="flex gap-2 border-b">
        {TABS.map(([key, label]) => (
          <button key={key} role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
                  className={`px-3 py-2 text-sm ${tab === key ? "border-b-2 border-blue-600 font-semibold" : "text-gray-500"}`}>
            {label}
          </button>
        ))}
      </div>
      {tab === "staff" && <Staff />}
      {tab === "profile" && <Profile />}
      {tab === "log" && <AccessLog />}
    </div>
  );
}
