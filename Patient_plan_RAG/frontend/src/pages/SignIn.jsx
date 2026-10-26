import React, { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { navigate } from "../utils/route";

export default function SignIn() {
  const { signIn } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await signIn(username.trim(), password);
    } catch (err) {
      setError(err.message.replace(/^\d+: /, ""));
      setPassword("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-sm mx-auto mt-16 bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-bold mb-1">Sign in</h2>
      <p className="text-sm text-gray-500 mb-5">Individuals and provider staff sign in here.</p>
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
            autoComplete="current-password"
            required
            maxLength={256}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full border rounded px-3 py-2"
          />
        </label>
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
          {busy ? "Please wait..." : "Sign in"}
        </button>
      </form>
      <p className="text-sm text-gray-600 mt-4">
        New here?{" "}
        <button type="button" onClick={() => navigate("/signup/individual")} className="text-blue-700 hover:underline">
          Sign up as an individual
        </button>{" "}
        or{" "}
        <button type="button" onClick={() => navigate("/signup/provider")} className="text-blue-700 hover:underline">
          as a provider
        </button>
      </p>
      <p className="text-xs text-gray-500 mt-4">
        Provider staff accounts are created by your organisation's administrator. Forgotten your
        password? Ask your organisation's administrator, or the platform administrator for
        personal accounts.
      </p>
    </div>
  );
}
