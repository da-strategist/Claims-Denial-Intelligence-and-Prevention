import React, { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { navigate } from "../utils/route";
import { PROVIDER_CATEGORIES } from "../utils/providers";

const MIN_LENGTH = 12;

function Field({ label, hint, ...props }) {
  return (
    <label className="block text-sm">
      <span className="font-medium text-gray-700">{label}</span>
      {props.children || <input {...props} className="mt-1 w-full border rounded px-3 py-2" />}
      {hint && <span className="block text-xs text-gray-500 mt-1">{hint}</span>}
    </label>
  );
}

/** Shared form shell: password rules, errors, submit, links back. */
function SignUpForm({ title, intro, onSubmit, children, footer }) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (password.length < MIN_LENGTH) return setError(`Use at least ${MIN_LENGTH} characters for the password.`);
    if (password !== confirm) return setError("The passwords don't match.");
    setBusy(true);
    try {
      await onSubmit(password);
    } catch (err) {
      setError(err.message.replace(/^\d+: /, ""));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-lg mx-auto mt-10 bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-bold mb-1">{title}</h2>
      <p className="text-sm text-gray-500 mb-5">{intro}</p>
      <form onSubmit={submit} className="space-y-4">
        {children}
        <Field label="Password" hint={`At least ${MIN_LENGTH} characters.`} type="password"
               autoComplete="new-password" required maxLength={256} value={password}
               onChange={(e) => setPassword(e.target.value)} />
        <Field label="Confirm password" type="password" autoComplete="new-password" required
               maxLength={256} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        {footer}
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        <button type="submit" disabled={busy}
                className="w-full bg-blue-600 text-white py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50">
          {busy ? "Please wait..." : "Create account"}
        </button>
      </form>
      <p className="text-sm text-gray-600 mt-4">
        Already have an account?{" "}
        <button type="button" onClick={() => navigate("/signin")} className="text-blue-700 hover:underline">Sign in</button>
        {" · "}
        <button type="button" onClick={() => navigate("/")} className="text-blue-700 hover:underline">Back</button>
      </p>
    </div>
  );
}

export function IndividualSignUp() {
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  return (
    <SignUpForm
      title="Sign up as an individual"
      intro="Upload your insurance policies and ask questions about your coverage. Only you can see what you upload."
      onSubmit={(password) => register(email.trim(), password)}
    >
      <Field label="Email" type="email" autoComplete="username" required maxLength={254}
             value={email} onChange={(e) => setEmail(e.target.value)} />
    </SignUpForm>
  );
}

const EMPTY_PROVIDER = { org_name: "", category: "", npi: "", address: "", city: "", phone: "",
                         full_name: "", username: "" };

export function ProviderSignUp() {
  const { registerProvider } = useAuth();
  const [form, setForm] = useState(EMPTY_PROVIDER);
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const trimmed = () => Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim()]));

  return (
    <SignUpForm
      title="Sign up as a provider"
      intro="For hospitals, clinics, pharmacies, labs and other providers. You'll be the organisation's administrator and can add staff once it's approved."
      onSubmit={(password) => registerProvider({ ...trimmed(), password })}
      footer={
        <p className="text-xs text-gray-500">
          The platform administrator reviews every provider before it can add patients, upload
          policies or receive policies from patients. You can sign in to check the status.
        </p>
      }
    >
      <fieldset className="space-y-4">
        <legend className="text-sm font-semibold text-gray-800 mb-2">Organisation</legend>
        <Field label="Organisation name" required maxLength={200} value={form.org_name} onChange={set("org_name")} />
        <Field label="Provider category">
          <select required value={form.category} onChange={set("category")}
                  className="mt-1 w-full border rounded px-3 py-2">
            <option value="">Choose a category…</option>
            {PROVIDER_CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </Field>
        <Field label="NPI (optional)" hint="10-digit National Provider Identifier, checked by the administrator."
               inputMode="numeric" pattern="\d{10}" maxLength={10} value={form.npi} onChange={set("npi")} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="City" required maxLength={100} value={form.city} onChange={set("city")} />
          <Field label="Phone (optional)" type="tel" maxLength={40} value={form.phone} onChange={set("phone")} />
        </div>
        <Field label="Address (optional)" maxLength={300} value={form.address} onChange={set("address")} />
      </fieldset>
      <fieldset className="space-y-4">
        <legend className="text-sm font-semibold text-gray-800 mb-2">You (the administrator)</legend>
        <Field label="Your full name" required maxLength={200} autoComplete="name" value={form.full_name}
               onChange={set("full_name")} />
        <Field label="Work email" type="email" required maxLength={254} autoComplete="username"
               value={form.username} onChange={set("username")} />
      </fieldset>
    </SignUpForm>
  );
}
