import React from "react";
import { navigate } from "../utils/route";

function Audience({ title, intro, points, action, path }) {
  return (
    <section className="bg-white rounded-lg shadow p-6 flex flex-col">
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="text-sm text-gray-600 mt-1">{intro}</p>
      <ul className="text-sm text-gray-700 mt-4 space-y-2 flex-1">
        {points.map((p) => (
          <li key={p} className="flex gap-2">
            <span aria-hidden="true" className="text-brand-700">✓</span>
            {p}
          </li>
        ))}
      </ul>
      <button onClick={() => navigate(path)}
              className="mt-6 bg-blue-600 text-white py-2 rounded text-sm hover:bg-blue-700">
        {action}
      </button>
    </section>
  );
}

/** Public landing page: what the app does, and the two ways to sign up. */
export default function Landing() {
  return (
    <div className="max-w-5xl mx-auto px-4 py-10 space-y-10">
      <div className="text-center max-w-2xl mx-auto">
        <h2 className="text-3xl font-bold">Understand your health insurance policy</h2>
        <p className="text-gray-600 mt-3">
          Upload a policy document and ask questions in plain words. Every answer quotes the
          policy, with the page and section it came from, so you can check it yourself.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Audience
          title="For individuals"
          intro="Your own insurance, in one place."
          points={[
            "Upload your policies, including more than one plan",
            "Ask what's covered, what you'll pay and what needs approval",
            "Share a policy with a provider, and stop sharing at any time",
          ]}
          action="Sign up as an individual"
          path="/signup/individual"
        />
        <Audience
          title="For providers"
          intro="Hospitals, clinics, pharmacies, labs and other providers."
          points={[
            "Keep each patient's policies on their record",
            "Check coverage and build prior-authorization checklists",
            "Receive policies patients choose to share with you",
          ]}
          action="Sign up as a provider"
          path="/signup/provider"
        />
      </div>

      <section className="bg-white rounded-lg shadow p-6">
        <h3 className="font-semibold mb-3">How it works</h3>
        <ol className="grid gap-4 md:grid-cols-3 text-sm text-gray-700">
          <li><strong className="block">1. Upload</strong>Add a policy PDF. Only you can see it.</li>
          <li><strong className="block">2. Ask</strong>Get answers quoted from the policy, with page numbers.</li>
          <li><strong className="block">3. Check</strong>Confirm anything important with your plan before you rely on it.</li>
        </ol>
      </section>

      <p className="text-center text-sm text-gray-600">
        Already have an account?{" "}
        <button onClick={() => navigate("/signin")} className="text-blue-700 hover:underline">Sign in</button>
      </p>
      <p className="text-center text-xs text-gray-500">
        Provider accounts are reviewed before they can receive patients' policies.
      </p>
    </div>
  );
}
