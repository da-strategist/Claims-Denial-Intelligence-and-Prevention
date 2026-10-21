import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Dashboard from "./Dashboard";
import Oversight from "./Oversight";
import { api } from "../services/api";

vi.mock("../services/api", () => ({
  api: {
    platformStats: vi.fn(), auditLog: vi.fn(), verifyAudit: vi.fn(), securityEvents: vi.fn(), listOrgs: vi.fn(),
  },
}));

const zeros = () => [0, 0, 0, 0, 0, 0, 0, 0];
const STATS = {
  weeks: ["2026-09-01", "2026-09-08", "2026-09-15", "2026-09-22", "2026-09-29", "2026-10-06", "2026-10-13", "2026-10-20"],
  accounts: { individuals: 12, provider_staff: 5, platform_admins: 1, disabled: 1 },
  providers: { by_status: { active: 3, pending: 2, rejected: 1 }, by_category: { Hospital: 2, Pharmacy: 1 } },
  sign_ups: { individuals: [0, 0, 1, 2, 0, 3, 4, 2], providers: zeros() },
  activity: { sign_ins: zeros(), questions: [0, 0, 0, 0, 0, 0, 5, 9], coverage_checks: zeros(),
              prior_auth_checklists: zeros(), uploads: zeros(), shares: zeros() },
  totals: { individual_policies: 14, provider_uploads: 6, samples: 4, shares: 7, connections: 8, patient_records: 9 },
};

afterEach(() => vi.clearAllMocks());

test("dashboard shows accounts, providers, sign-ups and activity as counts", async () => {
  api.platformStats.mockResolvedValue(STATS);
  render(<Dashboard />);
  expect(await screen.findByText("Waiting for approval")).toBeInTheDocument();
  expect(screen.getByText("12")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "Questions asked per week: 0, 0, 0, 0, 0, 0, 5, 9" })).toBeInTheDocument();
  expect(screen.getByText("14 in 8 weeks")).toBeInTheDocument();  // questions
  expect(screen.getByText("Pharmacy")).toBeInTheDocument();
  expect(screen.getByText(/No one's policies or questions are shown here/)).toBeInTheDocument();
});

const ENTRY = { ts: "2026-10-21T10:00:00+00:00", user: "alice@example.com", role: "individual", method: "GET",
                route: "/api/hospital/patients", document_id: null, patient_id: null, target: null,
                status: 403, client: "127.0.0.1", label: "Loaded hospital/patients", routine: false };

test("audit log: filter, page and check integrity", async () => {
  api.listOrgs.mockResolvedValue([{ org_id: "o1", name: "General Hospital" }]);
  api.auditLog.mockResolvedValue({ total: 150, entries: Array.from({ length: 100 }, () => ENTRY) });
  api.verifyAudit.mockResolvedValue({ ok: false, lines: 9, problem: "chain broken at line 3 (edited, inserted or deleted lines)" });
  render(<Oversight />);
  expect(await screen.findByText("150 matching entries, newest first")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("User"), "alice");
  await userEvent.selectOptions(screen.getByLabelText("Result"), "4xx");
  await userEvent.selectOptions(screen.getByLabelText("Provider staff"), "o1");
  await userEvent.click(screen.getByRole("button", { name: "Filter" }));
  expect(api.auditLog).toHaveBeenLastCalledWith({ user: "alice", route: "", status: "4xx", org_id: "o1",
                                                   since: "", until: "", include_routine: false,
                                                   limit: 100, offset: 0 });
  await userEvent.click(screen.getByRole("button", { name: "Load more" }));
  expect(api.auditLog).toHaveBeenLastCalledWith(expect.objectContaining({ user: "alice", offset: 100 }));
  await userEvent.click(screen.getByRole("button", { name: "Check integrity" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Tampering detected: chain broken at line 3");
});

test("security events are grouped by account", async () => {
  api.listOrgs.mockResolvedValue([]);
  api.auditLog.mockResolvedValue({ total: 0, entries: [] });
  api.securityEvents.mockResolvedValue({
    days: 7,
    failed_sign_ins: [{ user: "alice@example.com", count: 5, last: ENTRY.ts, clients: ["10.0.0.1"] }],
    lockouts: [], refused_requests: [],
    rejected_sign_ups: [{ org_id: "o9", name: "Fake Care", signed_up_by: "f@fake.example", reviewed_at: ENTRY.ts, review_note: "Not real" }],
  });
  render(<Oversight />);
  await userEvent.click(screen.getByRole("tab", { name: "Security events" }));
  const failed = (await screen.findByRole("heading", { name: "Failed sign-ins" })).closest("section");
  expect(within(failed).getByText("alice@example.com")).toBeInTheDocument();
  expect(within(failed).getByText("5")).toBeInTheDocument();
  expect(screen.getByText("Fake Care")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Period"), "30");
  await waitFor(() => expect(api.securityEvents).toHaveBeenLastCalledWith(30));
});
