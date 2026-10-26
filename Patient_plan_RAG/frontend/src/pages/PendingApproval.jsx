import React, { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { categoryLabel } from "../utils/providers";

/** Shown to a provider that signed itself up, until the platform admin approves it. */
export default function PendingApproval() {
  const { user, refresh, signOut } = useAuth();
  const [checked, setChecked] = useState(false);

  const check = async () => {
    await refresh();
    setChecked(true);
  };

  return (
    <div className="max-w-lg mx-auto mt-16 bg-white rounded-lg shadow p-6 space-y-4">
      <h2 className="text-xl font-bold">Your provider account is awaiting approval</h2>
      <p className="text-sm text-gray-700">
        Thanks for signing up <strong>{user.org_name}</strong> ({categoryLabel(user.org_category)}).
        The platform administrator reviews every provider before it can be used, so patients only
        ever share their policies with real providers.
      </p>
      <div className="text-sm text-gray-700">
        <p className="font-medium">Once approved you can:</p>
        <ul className="list-disc ml-5 mt-1 space-y-1">
          <li>add patients and upload their policies</li>
          <li>receive policies patients share with you</li>
          <li>add your staff</li>
        </ul>
      </div>
      <p className="text-xs text-gray-500">
        Signed in as {user.username}. There's no email notification yet: sign in again later, or
        check below.
      </p>
      {checked && <p role="status" className="text-sm text-gray-600">Still awaiting approval.</p>}
      <div className="flex gap-3">
        <button onClick={check} className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700">
          Check again
        </button>
        <button onClick={signOut} className="border px-4 py-2 rounded text-sm hover:bg-gray-50">
          Sign out
        </button>
      </div>
    </div>
  );
}
