import React, { useState } from "react";
import { useAuth } from "../auth/AuthContext";

const MIN_LENGTH = 12;

export default function SignIn() {
  const { signIn, register } = useAuth();
  const [creating, setCreating] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (creating) {
      if (password.length < MIN_LENGTH) return setError(`Use at least ${MIN_LENGTH} characters.`);
      if (password !== confirm) return setError("The passwords don't match.");
    }
    setBusy(true);
    try {
      if (creating) await register(username.trim(), password);
      else await signIn(username.trim(), password);
    } catch (err) {
      setError(err.message.replace(/^\d+: /, ""));
      setPassword("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-sm mx-auto mt-16 bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-bold mb-1">{creating ? "Create your account" : "Sign in"}</h2>
      <p className="text-sm text-gray-500 mb-5">
        {creating
          ? "For individuals: upload your insurance policy and ask questions about your coverage."
          : "Individuals and hospital staff sign in here."}
      </p>
      <form onSubmit={submit} className="space-y-4">
        <label className="block text-sm">
          <span className="font-medium text-gray-700">Email</span>
          <input
            type="email"
            autoComplete="username"
            required
            maxLength={254}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="mt-1 w-full border rounded px-3 py-2"
          />
        </label>
        <label className="block text-sm">
          <span className="font-medium text-gray-700">Password</span>
          <input
            type="password"
            autoComplete={creating ? "new-password" : "current-password"}
            required
            maxLength={256}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full border rounded px-3 py-2"
          />
        </label>
        {creating && (
          <label className="block text-sm">
            <span className="font-medium text-gray-700">Confirm password</span>
            <input
              type="password"
              autoComplete="new-password"
              required
              maxLength={256}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="mt-1 w-full border rounded px-3 py-2"
            />
          </label>
        )}
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
          {busy ? "Please wait..." : creating ? "Create account" : "Sign in"}
        </button>
      </form>
      <button
        type="button"
        onClick={() => {
          setCreating(!creating);
          setError("");
          setConfirm("");
        }}
        className="text-sm text-blue-700 hover:underline mt-4"
      >
        {creating ? "Already have an account? Sign in" : "New here? Create an account"}
      </button>
      <p className="text-xs text-gray-500 mt-4">
        Hospital staff accounts are created by your hospital's administrator. Forgotten your
        password? Ask your hospital administrator, or the platform administrator for personal
        accounts.
      </p>
    </div>
  );
}
