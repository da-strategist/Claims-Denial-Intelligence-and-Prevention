import React, { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { navigate } from "../utils/route";

const MIN_LENGTH = 12;

/** `forced`: shown after signing in with a temporary password. */
export default function ChangePassword({ forced = false }) {
  const { changePassword, signOut } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (next.length < MIN_LENGTH) return setError(`Use at least ${MIN_LENGTH} characters.`);
    if (next !== confirm) return setError("The new passwords don't match.");
    setBusy(true);
    try {
      await changePassword(current, next);
      setDone(true);
      setCurrent("");
      setNext("");
      setConfirm("");
      if (!forced) setTimeout(() => navigate("/"), 1200);
    } catch (err) {
      setError(err.message.replace(/^\d+: /, ""));
    } finally {
      setBusy(false);
    }
  };

  const field = (label, value, set, autoComplete) => (
    <label className="block text-sm">
      <span className="font-medium text-gray-700">{label}</span>
      <input
        type="password"
        autoComplete={autoComplete}
        required
        maxLength={256}
        value={value}
        onChange={(e) => set(e.target.value)}
        className="mt-1 w-full border rounded px-3 py-2"
      />
    </label>
  );

  return (
    <div className="max-w-sm mx-auto mt-10 bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-bold mb-1">
        {forced ? "Choose a new password" : "Change password"}
      </h2>
      <p className="text-sm text-gray-500 mb-5">
        {forced
          ? "You signed in with a temporary password. Choose your own to continue."
          : "Changing your password signs you out on other devices."}
      </p>
      {done && !forced && (
        <p role="status" className="text-sm text-green-700 mb-3">Password changed.</p>
      )}
      <form onSubmit={submit} className="space-y-4">
        {field(forced ? "Temporary password" : "Current password", current, setCurrent, "current-password")}
        {field(`New password (at least ${MIN_LENGTH} characters)`, next, setNext, "new-password")}
        {field("Confirm new password", confirm, setConfirm, "new-password")}
        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={busy}
          className="w-full bg-blue-600 text-white py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {busy ? "Saving..." : "Save password"}
        </button>
      </form>
      {forced && (
        <button onClick={signOut} className="text-xs text-gray-500 mt-4 hover:underline">
          Sign out instead
        </button>
      )}
    </div>
  );
}
