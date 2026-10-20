import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import { navigate } from "../utils/route";

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.dashboard().then(setStats).catch((e) => setError(e.message));
  }, []);

  if (error)
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded">
        Failed to load dashboard: {error}. Is the backend running on port 8001?
      </div>
    );
  if (!stats) return <div className="text-gray-500">Loading dashboard...</div>;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Dashboard</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Policies Loaded", value: stats.total_policies, color: "blue" },
          { label: "Pages Processed", value: stats.total_pages, color: "green" },
          { label: "Text Chunks", value: stats.total_chunks, color: "purple" },
          {
            label: "Mode",
            value: stats.mode === "demo" ? "Demo" : "Live",
            color: "amber",
          },
        ].map((card) => (
          <div
            key={card.label}
            className={`bg-white rounded-lg shadow p-5 border-t-4 border-${card.color}-500`}
          >
            <p className="text-sm text-gray-500">{card.label}</p>
            <p className="text-3xl font-bold mt-1">{card.value}</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-lg shadow p-5">
        <h3 className="text-lg font-semibold mb-3">Loaded Policies</h3>
        {stats.policies.length === 0 ? (
          <p className="text-gray-500">
            No policies loaded yet.{" "}
            <button
              onClick={() => navigate("/policies")}
              className="text-blue-600 underline"
            >
              Upload one
            </button>
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="py-2">Filename</th>
                <th>Insurer</th>
                <th>Plan</th>
                <th>Pages</th>
                <th>Chunks</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {stats.policies.map((p) => (
                <tr
                  key={p.document_id}
                  className="border-b hover:bg-gray-50 cursor-pointer"
                  onClick={() => navigate(`/policies/${p.document_id}`)}
                >
                  <td className="py-2 font-medium">{p.filename}</td>
                  <td>{p.insurer_name || "—"}</td>
                  <td>{p.plan_name || "—"}</td>
                  <td>{p.page_count}</td>
                  <td>{p.chunk_count}</td>
                  <td>
                    <span
                      className={`px-2 py-0.5 rounded text-xs ${
                        p.status === "completed"
                          ? "bg-green-100 text-green-700"
                          : "bg-yellow-100 text-yellow-700"
                      }`}
                    >
                      {p.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          {
            title: "Ask a Question",
            desc: "Chat with your policy documents using natural language",
            path: "/chat",
            icon: "💬",
          },
          {
            title: "Coverage Check",
            desc: "Assess whether a specific service is covered",
            path: "/coverage",
            icon: "🔍",
          },
          {
            title: "Prior Auth Prep",
            desc: "Generate a checklist for authorization requests",
            path: "/auth",
            icon: "📝",
          },
        ].map((card) => (
          <div
            key={card.path}
            onClick={() => navigate(card.path)}
            className="bg-white rounded-lg shadow p-5 hover:shadow-md cursor-pointer transition"
          >
            <p className="text-2xl mb-2">{card.icon}</p>
            <h4 className="font-semibold">{card.title}</h4>
            <p className="text-sm text-gray-500 mt-1">{card.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
