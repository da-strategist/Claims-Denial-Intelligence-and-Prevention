import React, { useEffect, useState } from "react";
import { api } from "../services/api";

const clean = (msg) => msg.replace(/^\d+: /, "");
const when = (iso) => (iso ? new Date(iso).toLocaleString() : "");
const PAGE = 100;
const EMPTY_FILTERS = { user: "", route: "", status: "", org_id: "", since: "", until: "", include_routine: false };

function AuditLog() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [applied, setApplied] = useState(EMPTY_FILTERS);
  const [orgs, setOrgs] = useState([]);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [check, setCheck] = useState(null);
  const [error, setError] = useState("");

  const load = (f, offset = 0) =>
    api.auditLog({ ...f, limit: PAGE, offset })
      .then((r) => {
        setRows((prev) => (offset ? [...prev, ...r.entries] : r.entries));
        setTotal(r.total);
      })
      .catch((e) => setError(clean(e.message)));

  useEffect(() => {
    load(EMPTY_FILTERS);
    api.listOrgs().then(setOrgs).catch(() => setOrgs([]));
  }, []);

  const set = (key) => (e) => setFilters({ ...filters, [key]: e.target.value });
  const apply = (e) => {
    e.preventDefault();
    setError("");
    setApplied(filters);
    load(filters);
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-600">
        Every request to the platform: who, what, which document, patient record or account, and
        the result. Questions, answers and documents are never recorded.
      </p>
      <form onSubmit={apply} className="bg-white rounded-lg shadow p-4 flex flex-wrap gap-3 items-end text-sm">
        <label>
          <span className="block text-gray-700">User</span>
          <input value={filters.user} onChange={set("user")} maxLength={254} className="border rounded px-2 py-1" />
        </label>
        <label>
          <span className="block text-gray-700">Route contains</span>
          <input value={filters.route} onChange={set("route")} maxLength={200} placeholder="/api/chat"
                 className="border rounded px-2 py-1" />
        </label>
        <label>
          <span className="block text-gray-700">Result</span>
          <select value={filters.status} onChange={set("status")} className="border rounded px-2 py-1">
            <option value="">Any</option>
            <option value="2xx">Succeeded (2xx)</option>
            <option value="4xx">Refused or invalid (4xx)</option>
            <option value="5xx">Server error (5xx)</option>
          </select>
        </label>
        <label>
          <span className="block text-gray-700">Provider staff</span>
          <select value={filters.org_id} onChange={set("org_id")} className="border rounded px-2 py-1">
            <option value="">Anyone</option>
            {orgs.map((o) => <option key={o.org_id} value={o.org_id}>{o.name}</option>)}
          </select>
        </label>
        <label>
          <span className="block text-gray-700">From</span>
          <input type="date" value={filters.since} onChange={set("since")} className="border rounded px-2 py-1" />
        </label>
        <label>
          <span className="block text-gray-700">To</span>
          <input type="date" value={filters.until} onChange={set("until")} className="border rounded px-2 py-1" />
        </label>
        <label className="flex items-center gap-1 self-center">
          <input type="checkbox" checked={filters.include_routine}
                 onChange={(e) => setFilters({ ...filters, include_routine: e.target.checked })} />
          Show page loads
        </label>
        <button type="submit" className="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">Filter</button>
        <button type="button" onClick={() => { setFilters(EMPTY_FILTERS); setApplied(EMPTY_FILTERS); load(EMPTY_FILTERS); }}
                className="text-gray-600 hover:underline">Clear</button>
      </form>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <button onClick={() => api.verifyAudit().then(setCheck).catch((e) => setError(clean(e.message)))}
                className="border px-3 py-1 rounded hover:bg-gray-50">Check integrity</button>
        {check && (
          <span role="status" className={check.ok ? "text-green-700" : "text-red-700 font-medium"}>
            {check.ok ? `Intact: ${check.lines} entries, none edited or removed.` : `Tampering detected: ${check.problem}.`}
          </span>
        )}
      </div>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}

      <div className="bg-white rounded-lg shadow overflow-x-auto">
        <p className="p-3 text-xs text-gray-500 border-b">{total} matching entr{total === 1 ? "y" : "ies"}, newest first</p>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="p-2">When</th><th>User</th><th>Action</th><th>Concerning</th><th>Result</th><th className="pr-2">Client</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e, i) => (
              <tr key={`${e.ts}-${i}`} className="border-b align-top">
                <td className="p-2 whitespace-nowrap">{when(e.ts)}</td>
                <td>{e.user || "—"}{e.role && <span className="block text-xs text-gray-500">{e.role}</span>}</td>
                <td className={e.routine ? "text-gray-500" : ""}>
                  {e.label}
                  <span className="block font-mono text-[11px] text-gray-400">{e.method} {e.route}</span>
                </td>
                <td className="text-xs text-gray-600">
                  {[e.document_id && `document ${e.document_id}`, e.patient_id && `patient ${e.patient_id}`,
                    e.target && `account ${e.target}`].filter(Boolean).join(" · ") || "—"}
                </td>
                <td className={e.status >= 400 ? "text-red-700" : ""}>{e.status}</td>
                <td className="text-xs text-gray-500 whitespace-nowrap pr-2">{e.client}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length < total && (
          <button onClick={() => load(applied, rows.length)} className="m-3 text-sm text-blue-700 hover:underline">
            Load more
          </button>
        )}
      </div>
    </div>
  );
}

function Group({ title, empty, rows }) {
  return (
    <section className="bg-white rounded-lg shadow">
      <h3 className="font-semibold p-4 border-b">{title}</h3>
      {rows.length === 0 ? (
        <p className="p-4 text-sm text-gray-500">{empty}</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500"><th className="p-2">Account</th><th>Times</th><th>Last</th><th>From</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.user} className="border-b">
                <td className="p-2">{r.user}</td><td>{r.count}</td><td>{when(r.last)}</td>
                <td className="text-xs text-gray-500">{r.clients.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function SecurityEvents() {
  const [days, setDays] = useState(7);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.securityEvents(days).then(setData).catch((e) => setError(clean(e.message)));
  }, [days]);

  if (error) return <p role="alert" className="text-sm text-red-600">{error}</p>;
  if (!data) return <p className="text-gray-500">Loading...</p>;
  return (
    <div className="space-y-4">
      <label className="text-sm flex items-center gap-2">
        Show the last
        <select aria-label="Period" value={days} onChange={(e) => setDays(Number(e.target.value))} className="border rounded px-2 py-1">
          {[1, 7, 30, 90].map((d) => <option key={d} value={d}>{d} day{d > 1 ? "s" : ""}</option>)}
        </select>
      </label>
      <Group title="Failed sign-ins" empty="None." rows={data.failed_sign_ins} />
      <Group title="Locked out after repeated failures" empty="None." rows={data.lockouts} />
      <Group title="Refused requests (not permitted or not found)" empty="None." rows={data.refused_requests} />
      <section className="bg-white rounded-lg shadow">
        <h3 className="font-semibold p-4 border-b">Rejected provider sign-ups</h3>
        {data.rejected_sign_ups.length === 0 ? (
          <p className="p-4 text-sm text-gray-500">None.</p>
        ) : (
          <ul className="divide-y text-sm">
            {data.rejected_sign_ups.map((o) => (
              <li key={o.org_id} className="p-3">
                <strong>{o.name}</strong> <span className="text-gray-500">by {o.signed_up_by} · {when(o.reviewed_at)}</span>
                {o.review_note && <span className="block text-xs text-gray-600">{o.review_note}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

const TABS = [["audit", "Audit log"], ["security", "Security events"]];

/** Platform admin: the audit log and security events. */
export default function Oversight() {
  const [tab, setTab] = useState("audit");
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">Audit & security</h2>
      <div role="tablist" className="flex gap-2 border-b">
        {TABS.map(([key, label]) => (
          <button key={key} role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
                  className={`px-3 py-2 text-sm -mb-px border-b-2 ${tab === key ? "border-blue-600 font-semibold" : "border-transparent text-gray-600"}`}>
            {label}
          </button>
        ))}
      </div>
      {tab === "audit" ? <AuditLog /> : <SecurityEvents />}
    </div>
  );
}
