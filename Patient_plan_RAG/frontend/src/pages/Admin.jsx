import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import { useAuth } from "../auth/AuthContext";

/** One-time display of a temporary password. */
function TemporaryPassword({ username, password, onDismiss }) {
  return (
    <div role="status" className="bg-amber-50 border border-amber-300 rounded p-4 mb-4 text-sm">
      <p className="font-semibold">Temporary password for {username}</p>
      <p className="font-mono text-base my-2 select-all">{password}</p>
      <p className="text-gray-600">
        Shown once. Give it to the member securely; they must change it at sign-in.
      </p>
      <button onClick={onDismiss} className="mt-2 text-blue-700 hover:underline">
        Done
      </button>
    </div>
  );
}

function PlanPicker({ plans, selected, onChange }) {
  if (plans.length === 0) return <p className="text-xs text-gray-500">No staff plans uploaded yet.</p>;
  return (
    <div className="flex flex-wrap gap-3">
      {plans.map((p) => (
        <label key={p.document_id} className="text-xs flex items-center gap-1">
          <input
            type="checkbox"
            checked={selected.includes(p.document_id)}
            onChange={(e) =>
              onChange(e.target.checked
                ? [...selected, p.document_id]
                : selected.filter((id) => id !== p.document_id))
            }
          />
          {p.plan_name || p.filename}
        </label>
      ))}
    </div>
  );
}

export default function Admin() {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [plans, setPlans] = useState([]);
  const [error, setError] = useState("");
  const [temp, setTemp] = useState(null);
  const [form, setForm] = useState({ username: "", role: "member", planIds: [] });
  const [editing, setEditing] = useState(null); // {username, planIds}

  const load = () =>
    Promise.all([api.listUsers(), api.listPolicies()])
      .then(([u, p]) => {
        setUsers(u);
        setPlans(p.filter((d) => !d.owner)); // staff plans only
      })
      .catch((e) => setError(e.message));
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

  const create = (e) => {
    e.preventDefault();
    act(async () => {
      const r = await api.createUser(form.username.trim(), form.role, form.planIds);
      setTemp({ username: r.username, password: r.temporary_password });
      setForm({ username: "", role: "member", planIds: [] });
    });
  };

  const planName = (id) => {
    const p = plans.find((d) => d.document_id === id);
    return p ? p.plan_name || p.filename : id;
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Members & plans</h2>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      {temp && <TemporaryPassword {...temp} onDismiss={() => setTemp(null)} />}

      <form onSubmit={create} className="bg-white rounded-lg shadow p-5 space-y-3">
        <h3 className="font-semibold">Add an account</h3>
        <div className="flex flex-wrap gap-3 items-end">
          <label className="text-sm">
            <span className="block text-gray-700">Email</span>
            <input
              type="email"
              required
              maxLength={254}
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              className="border rounded px-3 py-1.5"
            />
          </label>
          <label className="text-sm">
            <span className="block text-gray-700">Role</span>
            <select
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
              className="border rounded px-3 py-1.5"
            >
              <option value="member">Member (policyholder)</option>
              <option value="admin">Admin (staff)</option>
            </select>
          </label>
          <button type="submit" className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">
            Create
          </button>
        </div>
        {form.role === "member" && (
          <div>
            <p className="text-sm text-gray-700 mb-1">Plans this member can see</p>
            <PlanPicker plans={plans} selected={form.planIds}
                        onChange={(planIds) => setForm({ ...form, planIds })} />
          </div>
        )}
      </form>

      <div className="bg-white rounded-lg shadow">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="p-3">Email</th>
              <th>Role</th>
              <th>Plans</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.username} className="border-b align-top">
                <td className="p-3">{u.username}</td>
                <td className="capitalize">{u.role}</td>
                <td className="py-3 pr-3">
                  {editing?.username === u.username ? (
                    <div className="space-y-2">
                      <PlanPicker plans={plans} selected={editing.planIds}
                                  onChange={(planIds) => setEditing({ ...editing, planIds })} />
                      <button
                        onClick={() => act(async () => {
                          await api.updateUser(u.username, { plan_ids: editing.planIds });
                          setEditing(null);
                        })}
                        className="text-blue-700 text-xs hover:underline"
                      >
                        Save plans
                      </button>
                    </div>
                  ) : u.role === "admin" ? (
                    <span className="text-gray-400">All</span>
                  ) : (
                    u.plan_ids.map(planName).join(", ") || <span className="text-gray-400">None</span>
                  )}
                </td>
                <td>
                  {u.disabled ? "Disabled" : u.must_change_password ? "Awaiting first sign-in" : "Active"}
                </td>
                <td className="text-xs space-x-3 whitespace-nowrap pr-3">
                  {u.role === "member" && editing?.username !== u.username && (
                    <button onClick={() => setEditing({ username: u.username, planIds: u.plan_ids })}
                            className="text-blue-700 hover:underline">
                      Edit plans
                    </button>
                  )}
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
                    <button
                      onClick={() => act(() => api.updateUser(u.username, { disabled: !u.disabled }))}
                      className="text-red-700 hover:underline"
                    >
                      {u.disabled ? "Enable" : "Disable"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
