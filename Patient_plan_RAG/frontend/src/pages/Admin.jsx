import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import { useAuth } from "../auth/AuthContext";
import TemporaryPassword from "../components/TemporaryPassword";

const ROLE_LABELS = {
  individual: "Individual",
  hospital_staff: "Hospital staff",
  hospital_admin: "Hospital admin",
  platform_admin: "Platform admin",
};

/** Platform admin: onboard hospitals, manage accounts. No access to anyone's policies. */
export default function Admin() {
  const { user } = useAuth();
  const [orgs, setOrgs] = useState([]);
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");
  const [temp, setTemp] = useState(null);
  const [form, setForm] = useState({ name: "", adminUsername: "" });

  const load = () =>
    Promise.all([api.listOrgs(), api.listUsers()])
      .then(([o, u]) => {
        setOrgs(o);
        setUsers(u);
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

  const createOrg = (e) => {
    e.preventDefault();
    act(async () => {
      const r = await api.createOrg(form.name.trim(), form.adminUsername.trim());
      setTemp({ username: r.admin_username, password: r.temporary_password });
      setForm({ name: "", adminUsername: "" });
    });
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Hospitals & accounts</h2>
      <p className="text-sm text-gray-600">
        Add a hospital and its first hospital admin; they manage their own staff and patients.
        Platform admins never see individuals' or patients' policy documents.
      </p>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      {temp && <TemporaryPassword {...temp} onDismiss={() => setTemp(null)} />}

      <form onSubmit={createOrg} className="bg-white rounded-lg shadow p-5 flex flex-wrap gap-3 items-end">
        <label className="text-sm">
          <span className="block text-gray-700">Hospital name</span>
          <input required maxLength={200} value={form.name}
                 onChange={(e) => setForm({ ...form, name: e.target.value })}
                 className="border rounded px-3 py-1.5" />
        </label>
        <label className="text-sm">
          <span className="block text-gray-700">Hospital admin email</span>
          <input type="email" required maxLength={254} value={form.adminUsername}
                 onChange={(e) => setForm({ ...form, adminUsername: e.target.value })}
                 className="border rounded px-3 py-1.5" />
        </label>
        <button type="submit" className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">
          Add hospital
        </button>
      </form>

      <section className="bg-white rounded-lg shadow">
        <h3 className="font-semibold p-4 border-b">Hospitals</h3>
        {orgs.length === 0 ? (
          <p className="p-4 text-sm text-gray-500">No hospitals yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="p-3">Name</th>
                <th>Staff</th>
                <th>Patients</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {orgs.map((o) => (
                <tr key={o.org_id} className="border-b">
                  <td className="p-3">{o.name}</td>
                  <td>{o.staff_count}</td>
                  <td>{o.patient_count}</td>
                  <td>{o.disabled ? "Disabled" : "Active"}</td>
                  <td className="text-xs pr-3">
                    <button onClick={() => act(() => api.updateOrg(o.org_id, { disabled: !o.disabled }))}
                            className="text-red-700 hover:underline">
                      {o.disabled ? "Enable" : "Disable"}
                    </button>
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
              <th>Hospital</th>
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
