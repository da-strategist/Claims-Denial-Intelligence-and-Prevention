import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import { navigate } from "../utils/route";

const ACTIVITY_LABELS = {
  sign_ins: "Sign-ins",
  questions: "Questions asked",
  coverage_checks: "Coverage checks",
  prior_auth_checklists: "Prior-auth checklists",
  uploads: "Policies uploaded",
  shares: "Policies shared",
};

const STATUS_LABELS = { pending: "Pending approval", active: "Active", rejected: "Rejected", disabled: "Disabled" };

const shortWeek = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });

function Card({ label, value, onClick, tone = "" }) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag onClick={onClick} className={`bg-white rounded-lg shadow p-5 text-left ${onClick ? "hover:bg-gray-50" : ""}`}>
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${tone}`}>{value}</p>
    </Tag>
  );
}

/** Eight weekly bars, labelled with the count; no chart library needed. */
function WeeklyBars({ label, values, weeks }) {
  const max = Math.max(1, ...values);
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-700">{label}</span>
        <span className="text-gray-500">{values.reduce((a, b) => a + b, 0)} in 8 weeks</span>
      </div>
      <div className="flex items-end gap-1 h-16" role="img"
           aria-label={`${label} per week: ${values.join(", ")}`}>
        {values.map((v, i) => (
          <div key={weeks[i]} className="flex-1 flex flex-col items-center justify-end h-full"
               title={`Week of ${shortWeek(weeks[i])}: ${v}`}>
            <span className="text-[10px] text-gray-500">{v || ""}</span>
            <div className="w-full bg-brand-500 rounded-t" style={{ height: `${(v / max) * 100}%`, minHeight: v ? 2 : 0 }} />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Platform admin home: accounts, providers, sign-ups and activity (counts only). */
export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.platformStats().then(setStats).catch((e) => setError(e.message.replace(/^\d+: /, "")));
  }, []);

  if (error) return <p role="alert" className="text-red-600 text-sm">Couldn't load the dashboard: {error}</p>;
  if (!stats) return <p className="text-gray-500">Loading...</p>;

  const { accounts, providers, sign_ups: signUps, activity, totals, weeks } = stats;
  const pending = providers.by_status.pending || 0;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Dashboard</h2>
        <p className="text-sm text-gray-500">
          Counts from accounts, providers and the audit log. No one's policies or questions are shown here.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card label="Individuals" value={accounts.individuals} onClick={() => navigate("/admin")} />
        <Card label="Active providers" value={providers.by_status.active || 0} onClick={() => navigate("/admin")} />
        <Card label="Waiting for approval" value={pending} onClick={() => navigate("/admin")}
              tone={pending ? "text-amber-700" : ""} />
        <Card label="Provider staff" value={accounts.provider_staff} />
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <section className="bg-white rounded-lg shadow p-5 space-y-4">
          <h3 className="font-semibold">Sign-ups per week</h3>
          <WeeklyBars label="Individuals" values={signUps.individuals} weeks={weeks} />
          <WeeklyBars label="Providers" values={signUps.providers} weeks={weeks} />
        </section>
        <section className="bg-white rounded-lg shadow p-5 space-y-3">
          <h3 className="font-semibold">Providers</h3>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            {Object.entries(STATUS_LABELS).map(([key, label]) => (
              <div key={key} className="flex justify-between border-b py-1">
                <dt className="text-gray-600">{label}</dt><dd>{providers.by_status[key] || 0}</dd>
              </div>
            ))}
          </dl>
          <p className="text-sm font-medium text-gray-700 pt-2">Active, by category</p>
          {Object.keys(providers.by_category).length === 0 ? (
            <p className="text-sm text-gray-500">None yet.</p>
          ) : (
            <ul className="text-sm space-y-1">
              {Object.entries(providers.by_category).map(([cat, n]) => (
                <li key={cat} className="flex justify-between"><span>{cat}</span><span>{n}</span></li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="bg-white rounded-lg shadow p-5">
        <h3 className="font-semibold mb-4">Activity per week</h3>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {Object.entries(ACTIVITY_LABELS).map(([key, label]) => (
            <WeeklyBars key={key} label={label} values={activity[key]} weeks={weeks} />
          ))}
        </div>
      </section>

      <section className="bg-white rounded-lg shadow p-5">
        <h3 className="font-semibold mb-3">On the platform</h3>
        <dl className="grid gap-2 sm:grid-cols-3 text-sm">
          {[["Individuals' policies", totals.individual_policies], ["Provider uploads", totals.provider_uploads],
            ["Sample policies", totals.samples], ["Policies shared", totals.shares],
            ["Connections", totals.connections], ["Patient records", totals.patient_records],
            ["Disabled accounts", accounts.disabled], ["Platform admins", accounts.platform_admins]].map(([label, n]) => (
            <div key={label} className="flex justify-between border-b py-1">
              <dt className="text-gray-600">{label}</dt><dd>{n}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
