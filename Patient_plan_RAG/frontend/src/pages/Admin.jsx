import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import { useAuth } from "../auth/AuthContext";
import TemporaryPassword from "../components/TemporaryPassword";
import { PROVIDER_CATEGORIES, categoryLabel } from "../utils/providers";

const ROLE_LABELS = {
  individual: "Individual",
  hospital_staff: "Provider staff",
  hospital_admin: "Provider admin",
  platform_admin: "Platform admin",
};

const STATUS = {
  pending: ["Pending approval", "bg-amber-100 text-amber-800"],
  active: ["Active", "bg-green-100 text-green-800"],
  rejected: ["Rejected", "bg-red-100 text-red-800"],
};

function OrgStatus({ org }) {
  const [label, style] = org.disabled ? ["Disabled", "bg-gray-200 text-gray-700"] : STATUS[org.status] || [org.status, ""];
  return <span className={`px-2 py-0.5 rounded text-xs ${style}`}>{label}</span>;
}

const EMPTY = { name: "", adminUsername: "", category: "hospital", city: "" };

const day = (iso) => (iso ? iso.slice(0, 10) : "");

/** One self-signed-up provider waiting for review: details, a note, approve or reject. */
function PendingProvider({ org, act }) {
  const [note, setNote] = useState("");
  const detail = (label, value) => value && (
    <div><dt className="text-gray-500 text-xs">{label}</dt><dd>{value}</dd></div>
  );
  return (
    <li className="p-4 space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <strong>{org.name}</strong>
        <span className="text-xs text-gray-500">Signed up {day(org.created_at)}</span>
      </div>
      <dl className="grid gap-3 sm:grid-cols-3 text-sm">
        {detail("Category", categoryLabel(org.category))}
        {detail("NPI", org.npi || "Not given")}
        {detail("Location", [org.address, org.city].filter(Boolean).join(", "))}
        {detail("Signed up by", `${org.signed_up_by_name || ""} ${org.signed_up_by}`.trim())}
        {detail("Phone", org.phone)}
      </dl>
      <div className="flex flex-wrap gap-2 items-center text-sm">
        <input aria-label={`Note for ${org.name}`} placeholder="Note (shown to the provider if rejected)"
               maxLength={500} value={note} onChange={(e) => setNote(e.target.value)}
               className="border rounded px-2 py-1 flex-1 min-w-[16rem]" />
        <button onClick={() => act(() => api.approveOrg(org.org_id, note.trim()))}
                className="bg-green-700 text-white px-3 py-1 rounded hover:bg-green-800">
          Approve
        </button>
        <button onClick={() => act(() => api.rejectOrg(org.org_id, note.trim()))}
                className="border border-red-300 text-red-700 px-3 py-1 rounded hover:bg-red-50">
          Reject
        </button>
      </div>
    </li>
  );
}

/** Platform admin: review provider sign-ups, add providers, manage accounts.
 *  No access to anyone's policies. */
export default function Admin() {
  const { user } = useAuth();
  const [orgs, setOrgs] = useState([]);
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");
  const [temp, setTemp] = useState(null);
  const [form, setForm] = useState(EMPTY);

  const load = () =>
    Promise.all([api.listOrgs(), api.listUsers()])
      .then(([o, u]) => {
        setOrgs(o);
        setUsers(u);
      })
      .catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const pending = orgs.filter((o) => o.status === "pending");
  const reviewed = orgs.filter((o) => o.status !== "pending");

  const act = async (fn) => {
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e.message.replace(/^\d+: /, ""));
    }
  };

  const createOrg = (e) => {
    e.preventDefault();
    act(async () => {
      const r = await api.createOrg({ name: form.name.trim(), adminUsername: form.adminUsername.trim(),
                                      category: form.category, city: form.city.trim() });
      setTemp({ username: r.admin_username, password: r.temporary_password });
      setForm(EMPTY);
    });
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Providers & accounts</h2>
      <p className="text-sm text-gray-600">
        Providers sign themselves up and wait for your approval, or you add one here with its
        first provider admin. They manage their own staff and patients. Platform admins never see
        individuals' or patients' policy documents.
      </p>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      {temp && <TemporaryPassword {...temp} onDismiss={() => setTemp(null)} />}

      <section className="bg-white rounded-lg shadow">
        <h3 className="font-semibold p-4 border-b">
          Waiting for approval{pending.length > 0 && ` (${pending.length})`}
        </h3>
        {pending.length === 0 ? (
          <p className="p-4 text-sm text-gray-500">No provider sign-ups are waiting.</p>
        ) : (
          <>
            <p className="px-4 pt-3 text-xs text-gray-500">
              Check the organisation is real before approving: once approved, individuals can find
              it and share their policies with it. NPIs are not checked automatically.
            </p>
            <ul className="divide-y">
              {pending.map((o) => <PendingProvider key={o.org_id} org={o} act={act} />)}
            </ul>
          </>
        )}
      </section>

      <form onSubmit={createOrg} className="bg-white rounded-lg shadow p-5 flex flex-wrap gap-3 items-end">
        <label className="text-sm">
          <span className="block text-gray-700">Provider name</span>
          <input required maxLength={200} value={form.name}
                 onChange={(e) => setForm({ ...form, name: e.target.value })}
                 className="border rounded px-3 py-1.5" />
        </label>
        <label className="text-sm">
          <span className="block text-gray-700">Provider admin email</span>
          <input type="email" required maxLength={254} value={form.adminUsername}
                 onChange={(e) => setForm({ ...form, adminUsername: e.target.value })}
                 className="border rounded px-3 py-1.5" />
        </label>
        <label className="text-sm">
          <span className="block text-gray-700">Category</span>
          <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}
                  className="border rounded px-3 py-1.5">
            {PROVIDER_CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label className="text-sm">
          <span className="block text-gray-700">City</span>
          <input maxLength={100} value={form.city}
                 onChange={(e) => setForm({ ...form, city: e.target.value })}
                 className="border rounded px-3 py-1.5" />
        </label>
        <button type="submit" className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">
          Add provider
        </button>
      </form>

      <section className="bg-white rounded-lg shadow">
        <h3 className="font-semibold p-4 border-b">Providers</h3>
        {reviewed.length === 0 ? (
          <p className="p-4 text-sm text-gray-500">No providers yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="p-3">Name</th>
                <th>Category</th>
                <th>City</th>
                <th>Staff</th>
                <th>Patients</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {reviewed.map((o) => (
                <tr key={o.org_id} className="border-b">
                  <td className="p-3">{o.name}</td>
                  <td>{categoryLabel(o.category)}</td>
                  <td>{o.city || "—"}</td>
                  <td>{o.staff_count}</td>
                  <td>{o.patient_count}</td>
                  <td>
                    <OrgStatus org={o} />
                    {o.status === "rejected" && o.review_note && (
                      <span className="block text-xs text-gray-500">{o.review_note}</span>
                    )}
                  </td>
                  <td className="text-xs pr-3 whitespace-nowrap">
                    {o.status === "rejected" ? (
                      <button onClick={() => act(() => api.approveOrg(o.org_id))}
                              className="text-green-800 hover:underline">
                        Approve after all
                      </button>
                    ) : (
                      <button onClick={() => act(() => api.updateOrg(o.org_id, { disabled: !o.disabled }))}
                              className="text-red-700 hover:underline">
                        {o.disabled ? "Enable" : "Disable"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="bg-white rounded-lg shadow">
        <h3 className="font-semibold p-4 border-b">Accounts</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="p-3">Email</th>
              <th>Type</th>
              <th>Provider</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.username} className="border-b">
                <td className="p-3">{u.username}</td>
                <td>{ROLE_LABELS[u.role] || u.role}</td>
                <td>{u.org_name || "—"}</td>
                <td>{u.disabled ? "Disabled" : u.must_change_password ? "Awaiting first sign-in" : "Active"}</td>
                <td className="text-xs space-x-3 whitespace-nowrap pr-3">
                  <button
                    onClick={() => act(async () => {
                      const r = await api.resetPassword(u.username);
                      setTemp({ username: r.username, password: r.temporary_password });
                    })}
                    className="text-blue-700 hover:underline"
                  >
                    Reset password
                  </button>
                  {u.username !== user.username && (
                    <button onClick={() => act(() => api.updateUser(u.username, { disabled: !u.disabled }))}
                            className="text-red-700 hover:underline">
                      {u.disabled ? "Enable" : "Disable"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
