import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import { useAuth } from "../auth/AuthContext";
import TemporaryPassword from "../components/TemporaryPassword";

const ROLE_LABELS = { hospital_staff: "Staff", hospital_admin: "Provider admin" };

/** Provider admins manage their own organisation's staff accounts. */
export default function Staff() {
  const { user } = useAuth();
  const [staff, setStaff] = useState([]);
  const [error, setError] = useState("");
  const [temp, setTemp] = useState(null);
  const [form, setForm] = useState({ username: "", role: "hospital_staff" });

  const load = () => api.listStaff().then(setStaff).catch((e) => setError(e.message));
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

  const add = (e) => {
    e.preventDefault();
    act(async () => {
      const r = await api.addStaff(form.username.trim(), form.role);
      setTemp({ username: r.username, password: r.temporary_password });
      setForm({ username: "", role: "hospital_staff" });
    });
  };

  return (
    <div className="space-y-6">
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      {temp && <TemporaryPassword {...temp} onDismiss={() => setTemp(null)} />}

      <form onSubmit={add} className="bg-white rounded-lg shadow p-5 flex flex-wrap gap-3 items-end">
        <label className="text-sm">
          <span className="block text-gray-700">Email</span>
          <input type="email" required maxLength={254} value={form.username}
                 onChange={(e) => setForm({ ...form, username: e.target.value })}
                 className="border rounded px-3 py-1.5" />
        </label>
        <label className="text-sm">
          <span className="block text-gray-700">Role</span>
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}
                  className="border rounded px-3 py-1.5">
            <option value="hospital_staff">Staff</option>
            <option value="hospital_admin">Provider admin</option>
          </select>
        </label>
        <button type="submit" className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">
          Add staff
        </button>
      </form>

      <div className="bg-white rounded-lg shadow">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="p-3">Email</th>
              <th>Role</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {staff.map((u) => (
              <tr key={u.username} className="border-b">
                <td className="p-3">{u.username}</td>
                <td>{ROLE_LABELS[u.role] || u.role}</td>
                <td>{u.disabled ? "Disabled" : u.must_change_password ? "Awaiting first sign-in" : "Active"}</td>
                <td className="text-xs space-x-3 whitespace-nowrap pr-3">
                  <button
                    onClick={() => act(async () => {
                      const r = await api.resetStaffPassword(u.username);
                      setTemp({ username: r.username, password: r.temporary_password });
                    })}
                    className="text-blue-700 hover:underline"
                  >
                    Reset password
                  </button>
                  {u.username !== user.username && (
                    <button onClick={() => act(() => api.updateStaff(u.username, { disabled: !u.disabled }))}
                            className="text-red-700 hover:underline">
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
