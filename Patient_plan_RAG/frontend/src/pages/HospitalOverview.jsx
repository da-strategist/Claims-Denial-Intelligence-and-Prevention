import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import { navigate } from "../utils/route";

const fmt = (iso) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString() : "—");

function PlanList({ rows, empty }) {
  if (rows.length === 0) return <p className="text-sm text-gray-500">{empty}</p>;
  return (
    <ul className="text-sm space-y-1">
      {rows.map((r) => (
        <li key={`${r.patient_id}-${r.document_id}`}>
          <button onClick={() => navigate(`/patients/${r.patient_id}`)} className="text-blue-700 hover:underline">
            {r.patient_name}
          </button>{" "}
          <span className="text-gray-500">· {r.plan} · ends {fmt(r.expiration_date)}</span>
        </li>
      ))}
    </ul>
  );
}

/** Provider landing page: patients, plans ended or ending soon, shares to
 *  file, people who added the provider. */
export default function HospitalOverview() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.hospitalOverview().then(setData).catch((e) => setError(e.message.replace(/^\d+: /, "")));
  }, []);

  if (error) return <p role="alert" className="text-red-600 text-sm">Couldn't load the overview: {error}</p>;
  if (!data) return <p className="text-gray-500">Loading...</p>;

  const card = (label, value, onClick) => (
    <button onClick={onClick} className="bg-white rounded-lg shadow p-5 text-left hover:bg-gray-50">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
    </button>
  );

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Overview</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {card("Patients", data.patient_count, () => navigate("/patients"))}
        {card("Plans ended", data.plans_ended.length, () => {})}
        {card(`Ending within ${data.ending_soon_days} days`, data.plans_ending_soon.length, () => {})}
        {card(`Shared in the last ${data.new_share_days} days`, data.recent_shares.length, () => navigate("/shared"))}
        {card("New patients who added you", data.unlinked_connections.length, () => navigate("/shared"))}
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        <section className="bg-white rounded-lg shadow p-5">
          <h3 className="font-semibold mb-2">Plans ending within {data.ending_soon_days} days</h3>
          <PlanList rows={data.plans_ending_soon} empty="None. Coverage dates come from each policy document." />
        </section>
        <section className="bg-white rounded-lg shadow p-5">
          <h3 className="font-semibold mb-2">Plans that have ended</h3>
          <PlanList rows={data.plans_ended} empty="None." />
        </section>
      </div>
      <section className="bg-white rounded-lg shadow p-5">
        <h3 className="font-semibold mb-2">Patients who added you, not yet attached to a record</h3>
        {data.unlinked_connections.length === 0 ? (
          <p className="text-sm text-gray-500">Nothing waiting.</p>
        ) : (
          <ul className="text-sm space-y-1">
            {data.unlinked_connections.map((c) => (
              <li key={c.connection_id}>
                {c.name || c.email}{c.name && <span className="text-gray-500"> · {c.email}</span>}
                {c.is_new && <span className="ml-2 bg-blue-100 text-blue-800 px-2 py-0.5 rounded text-xs">New</span>}{" "}
                <button onClick={() => navigate("/shared")} className="text-blue-700 hover:underline">Attach</button>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="bg-white rounded-lg shadow p-5">
        <h3 className="font-semibold mb-2">Recently shared with you</h3>
        {data.recent_shares.length === 0 ? (
          <p className="text-sm text-gray-500">Nothing in the last {data.new_share_days} days.</p>
        ) : (
          <ul className="text-sm space-y-1">
            {data.recent_shares.map((s) => (
              <li key={s.share_id}>
                {s.plan_name || s.filename} from {s.shared_by_name || s.shared_by}{" "}
                {s.patient_id ? (
                  <button onClick={() => navigate(`/patients/${s.patient_id}`)} className="text-blue-700 hover:underline">
                    Open {s.patient_name}'s record
                  </button>
                ) : (
                  <button onClick={() => navigate("/shared")} className="text-blue-700 hover:underline">File it</button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
      {data.unfiled_shares.length > 0 && (
        <section className="bg-white rounded-lg shadow p-5">
          <h3 className="font-semibold mb-2">Shared with you, not filed</h3>
          <ul className="text-sm space-y-1">
            {data.unfiled_shares.map((s) => (
              <li key={s.share_id}>
                {s.plan_name || s.filename} from {s.shared_by_name || s.shared_by}{" "}
                <button onClick={() => navigate("/shared")} className="text-blue-700 hover:underline">File it</button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
