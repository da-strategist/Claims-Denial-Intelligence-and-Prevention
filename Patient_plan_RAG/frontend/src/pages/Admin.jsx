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

const when = (iso) => (iso ? new Date(iso).toLocaleString() : "Never");

/** Typed confirmation before deleting: the exact email or provider name. */
function ConfirmDelete({ what, expected, onDelete, onCancel }) {
  const [typed, setTyped] = useState("");
  return (
    <div role="alertdialog" aria-label={`Delete ${expected}`} className="border border-red-200 bg-red-50 rounded p-3 text-sm space-y-2">
      <p>{what} This can't be undone. Type <strong>{expected}</strong> to confirm.</p>
      <div className="flex flex-wrap gap-2">
        <input aria-label="Type to confirm" value={typed} onChange={(e) => setTyped(e.target.value)}
               maxLength={254} className="border rounded px-2 py-1" />
        <button disabled={typed.trim() !== expected} onClick={() => onDelete(typed.trim())}
                className="bg-red-600 text-white px-3 py-1 rounded disabled:opacity-50">Delete</button>
        <button onClick={onCancel} className="text-gray-600 hover:underline">Cancel</button>
      </div>
    </div>
  );
}

/** One account: details and what it holds (counts only). Individuals can be deleted. */
function AccountDetail({ username, act, onClose }) {
  const [d, setD] = useState(null);
  const [deleting, setDeleting] = useState(false);
  useEffect(() => { api.userDetail(username).then(setD).catch(() => setD(null)); }, [username]);
  if (!d) return null;
  const row = (label, value) => (
    <div className="flex justify-between border-b py-1"><dt className="text-gray-600">{label}</dt><dd>{value}</dd></div>
  );
  return (
    <section aria-label={`Account ${username}`} className="bg-white rounded-lg shadow p-5 space-y-3">
      <div className="flex justify-between items-baseline">
        <h3 className="font-semibold">{d.full_name || d.username}</h3>
        <button onClick={onClose} className="text-sm text-gray-500 hover:underline">Close</button>
      </div>
      <dl className="grid gap-x-6 sm:grid-cols-2 text-sm">
        {row("Email", d.username)}
        {row("Type", ROLE_LABELS[d.role] || d.role)}
        {d.org_name && row("Provider", d.org_name)}
        {row("Status", d.disabled ? "Disabled" : d.must_change_password ? "Awaiting first sign-in" : "Active")}
        {row("Created", when(d.created_at))}
        {row("Last sign-in", when(d.last_sign_in))}
        {d.holds && row("Policies", d.holds.policies)}
        {d.holds && row("Policies shared", d.holds.shares)}
        {d.holds && row("Providers listed", `${d.holds.providers} (${d.holds.connected_providers} on the platform)`)}
      </dl>
      <p className="text-xs text-gray-500">Counts only: platform admins never see anyone's policies.</p>
      {d.role === "individual" && (deleting ? (
        <ConfirmDelete expected={d.username}
                       what="Delete this account, its policies, shares and providers list? Providers lose access to its policies at once."
                       onCancel={() => setDeleting(false)}
                       onDelete={(confirm) => act(async () => { await api.deleteUser(d.username, confirm); onClose(); })} />
      ) : (
        <button onClick={() => setDeleting(true)} className="text-sm text-red-700 hover:underline">Delete account (spam)</button>
      ))}
    </section>
  );
}

/** A provider's details as it entered them: view only. Rejected sign-ups can be deleted. */
function ProviderDetail({ orgId, act, onClose }) {
  const [d, setD] = useState(null);
  const [deleting, setDeleting] = useState(false);
  useEffect(() => { api.orgDetail(orgId).then(setD).catch(() => setD(null)); }, [orgId]);
  if (!d) return null;
  const row = (label, value) => value ? (
    <div className="flex justify-between border-b py-1"><dt className="text-gray-600">{label}</dt><dd>{value}</dd></div>
  ) : null;
  return (
    <section aria-label={`Provider ${d.name}`} className="bg-white rounded-lg shadow p-5 space-y-3">
      <div className="flex justify-between items-baseline">
        <h3 className="font-semibold">{d.name} <OrgStatus org={d} /></h3>
        <button onClick={onClose} className="text-sm text-gray-500 hover:underline">Close</button>
      </div>
      <dl className="grid gap-x-6 sm:grid-cols-2 text-sm">
        {row("Category", d.category_label)}
        {row("NPI", d.npi || "Not given")}
        {row("Address", [d.address, d.city].filter(Boolean).join(", "))}
        {row("Phone", d.phone)}
        {row("Contact email", d.contact_email)}
        {row("Signed up by", d.signed_up_by && `${d.signed_up_by_name || ""} ${d.signed_up_by}`.trim())}
        {row("Joined", when(d.created_at))}
        {row("Reviewed", d.reviewed_at && `${when(d.reviewed_at)} by ${d.reviewed_by}`)}
        {row("Review note", d.review_note)}
        {row("Patient records", String(d.patient_count))}
        {row("People connected", String(d.connection_count))}
        {row("Policies shared with it", String(d.share_count))}
      </dl>
      <p className="text-xs text-gray-500">
        Details are the provider's own. Changes are made by the provider's admin, not here.
      </p>
      <div>
        <p className="text-sm font-medium mb-1">Staff</p>
        <ul className="text-sm space-y-1">
          {d.staff.map((u) => (
            <li key={u.username} className="flex flex-wrap gap-2">
              <span>{u.full_name ? `${u.full_name} · ` : ""}{u.username}</span>
              <span className="text-gray-500">{ROLE_LABELS[u.role]}</span>
              <span className="text-gray-500">· last sign-in {when(u.last_sign_in)}</span>
              {u.disabled && <span className="text-red-700">· disabled</span>}
            </li>
          ))}
        </ul>
      </div>
      {d.status === "rejected" && (deleting ? (
        <ConfirmDelete expected={d.name} what="Delete this rejected sign-up and its accounts?"
                       onCancel={() => setDeleting(false)}
                       onDelete={(confirm) => act(async () => { await api.deleteOrg(d.org_id, confirm); onClose(); })} />
      ) : (
        <button onClick={() => setDeleting(true)} className="text-sm text-red-700 hover:underline">Delete rejected sign-up</button>
      ))}
    </section>
  );
}

const ACCOUNT_FILTERS = [["", "All types"], ["individual", "Individuals"], ["hospital_admin", "Provider admins"],
                         ["hospital_staff", "Provider staff"], ["platform_admin", "Platform admins"]];

/** Platform admin: review provider sign-ups, add providers, manage accounts.
 *  No access to anyone's policies, and provider details are view-only. */
export default function Admin() {
  const { user, refresh } = useAuth();
  const [orgs, setOrgs] = useState([]);
  const [search, setSearch] = useState({ text: "", role: "", status: "" });
  const [openAccount, setOpenAccount] = useState(null);
  const [openProvider, setOpenProvider] = useState(null);
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
  const q = search.text.trim().toLowerCase();
  const shownUsers = users.filter((u) =>
    (!q || [u.username, u.full_name, u.org_name].some((v) => (v || "").toLowerCase().includes(q)))
    && (!search.role || u.role === search.role)
    && (!search.status || (search.status === "disabled" ? u.disabled
      : search.status === "first" ? !u.disabled && u.must_change_password
      : !u.disabled && !u.must_change_password)));
  const reviewed = orgs.filter((o) => o.status !== "pending");

  const act = async (fn) => {
    setError("");
    try {
      await fn();
      await load();
      refresh?.(); // the navigation's pending count
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
        <div className="w-full">
          <h3 className="font-semibold">Add a provider directly</h3>
          <p className="text-xs text-gray-500">Active at once, no approval step. Its admin gets a temporary password.</p>
        </div>
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

      {openProvider && <ProviderDetail key={openProvider} orgId={openProvider} act={act} onClose={() => setOpenProvider(null)} />}
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
                  <td className="p-3">
                    <button onClick={() => setOpenProvider(o.org_id)} className="text-blue-700 hover:underline text-left">
                      {o.name}
                    </button>
                  </td>
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

      {openAccount && <AccountDetail key={openAccount} username={openAccount} act={act} onClose={() => setOpenAccount(null)} />}
      <section className="bg-white rounded-lg shadow">
        <div className="p-4 border-b flex flex-wrap items-center gap-3">
          <h3 className="font-semibold mr-auto">Accounts</h3>
          <input aria-label="Search accounts" placeholder="Search email, name or provider" maxLength={254}
                 value={search.text} onChange={(e) => setSearch({ ...search, text: e.target.value })}
                 className="border rounded px-2 py-1 text-sm w-64" />
          <select aria-label="Account type" value={search.role} onChange={(e) => setSearch({ ...search, role: e.target.value })}
                  className="border rounded px-2 py-1 text-sm">
            {ACCOUNT_FILTERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <select aria-label="Account status" value={search.status} onChange={(e) => setSearch({ ...search, status: e.target.value })}
                  className="border rounded px-2 py-1 text-sm">
            <option value="">Any status</option>
            <option value="active">Active</option>
            <option value="disabled">Disabled</option>
            <option value="first">Awaiting first sign-in</option>
          </select>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="p-3">Email</th>
              <th>Type</th>
              <th>Provider</th>
              <th>Status</th>
              <th>Last sign-in</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {shownUsers.map((u) => (
              <tr key={u.username} className="border-b">
                <td className="p-3">
                  <button onClick={() => setOpenAccount(u.username)} className="text-blue-700 hover:underline text-left">
                    {u.username}
                  </button>
                  {u.full_name && <span className="block text-xs text-gray-500">{u.full_name}</span>}
                </td>
                <td>{ROLE_LABELS[u.role] || u.role}</td>
                <td>{u.org_name || "—"}</td>
                <td>{u.disabled ? "Disabled" : u.must_change_password ? "Awaiting first sign-in" : "Active"}</td>
                <td className="text-xs text-gray-500">{u.last_sign_in ? new Date(u.last_sign_in).toLocaleDateString() : "Never"}</td>
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
        {shownUsers.length === 0 && <p className="p-4 text-sm text-gray-500">No accounts match.</p>}
      </section>
    </div>
  );
}
