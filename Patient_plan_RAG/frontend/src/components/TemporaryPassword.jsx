import React from "react";

/** One-time display of a temporary password for a new or reset account. */
export default function TemporaryPassword({ username, password, onDismiss }) {
  return (
    <div role="status" className="bg-amber-50 border border-amber-300 rounded p-4 mb-4 text-sm">
      <p className="font-semibold">Temporary password for {username}</p>
      <p className="font-mono text-base my-2 select-all">{password}</p>
      <p className="text-gray-600">
        Shown once. Give it to them securely; they must change it when they sign in.
      </p>
      <button onClick={onDismiss} className="mt-2 text-blue-700 hover:underline">
        Done
      </button>
    </div>
  );
}
