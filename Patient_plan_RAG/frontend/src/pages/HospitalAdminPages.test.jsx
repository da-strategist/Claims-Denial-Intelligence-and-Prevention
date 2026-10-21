import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import HospitalOverview from "./HospitalOverview";
import HospitalAdmin from "./HospitalAdmin";
import PriorAuth from "./PriorAuth";
import { api } from "../services/api";

vi.mock("../services/api", () => ({
  api: {
    hospitalOverview: vi.fn(), getHospitalProfile: vi.fn(), updateHospitalProfile: vi.fn(),
    accessLog: vi.fn(), listStaff: vi.fn(), listPolicies: vi.fn(), listPatients: vi.fn(),
    authChecklist: vi.fn(), saveChecklist: vi.fn(),
  },
}));
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: { username: "ha@h.example", role: "hospital_admin", org_id: "o1" } }),
}));

afterEach(() => vi.clearAllMocks());

test("overview shows counts, ending plans and shares to file", async () => {
  api.hospitalOverview.mockResolvedValue({
    patient_count: 3, archived_count: 1, ending_soon_days: 30,
    plans_ended: [{ patient_id: "p1", patient_name: "Pat One", document_id: "d1", plan: "Gold PPO", expiration_date: "2025-12-31" }],
    plans_ending_soon: [{ patient_id: "p2", patient_name: "Bea Two", document_id: "d2", plan: "Silver HMO", expiration_date: "2026-12-31" }],
    unfiled_shares: [{ share_id: "s1", plan_name: "Gold PPO", shared_by: "alice@example.com", shared_by_name: "Alice Smith", is_new: true }],
  });
  render(<HospitalOverview />);
  expect(await screen.findByText("Bea Two")).toBeInTheDocument();
  expect(screen.getByText("Pat One")).toBeInTheDocument();
  expect(screen.getByText(/from Alice Smith/)).toBeInTheDocument();
  expect(screen.getByText("New")).toBeInTheDocument();
  expect(screen.getByText("Ending within 30 days")).toBeInTheDocument();
});

test("hospital admin edits the hospital profile", async () => {
  api.listStaff.mockResolvedValue([]);
  api.getHospitalProfile.mockResolvedValue({ org_id: "o1", name: "General Hospital", address: "", city: "", phone: "", contact_email: "" });
  api.updateHospitalProfile.mockImplementation(async (p) => ({ org_id: "o1", name: "General Hospital", ...p }));
  render(<HospitalAdmin />);
  await userEvent.click(screen.getByRole("tab", { name: "Hospital profile" }));
  await userEvent.type(await screen.findByLabelText("City"), "Springfield");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(api.updateHospitalProfile).toHaveBeenCalledWith({ address: "", city: "Springfield", phone: "", contact_email: "" });
  expect(await screen.findByRole("status")).toHaveTextContent("Profile saved");
});

test("access log lists staff activity in plain words and filters", async () => {
  api.listStaff.mockResolvedValue([]);
  api.accessLog.mockResolvedValue([
    { ts: "2026-10-21T10:00:00Z", user: "gs@h.example", method: "GET", route: "/api/hospital/patients/{patient_id}",
      patient_id: "p1", patient_name: "Pat One", status: 200 },
    { ts: "2026-10-21T09:00:00Z", user: "nurse@h.example", method: "POST", route: "/api/chat",
      patient_id: "p2", patient_name: "Bea Two", status: 404 },
  ]);
  render(<HospitalAdmin />);
  await userEvent.click(screen.getByRole("tab", { name: "Access log" }));
  expect(await screen.findByText("Opened patient record")).toBeInTheDocument();
  expect(screen.getByText("Asked a question")).toBeInTheDocument();
  expect(screen.getByText("Refused (404)")).toBeInTheDocument();
  await userEvent.type(screen.getByPlaceholderText(/Filter/), "pat one");
  expect(screen.queryByText("Bea Two")).toBeNull();
});

test("prior auth: pick the patient, generate, and save to their record", async () => {
  window.location.hash = "/auth?patient=p1";
  api.listPolicies.mockResolvedValue([{ document_id: "d1", filename: "p1.pdf", org_id: "o1", patient_id: "p1" }]);
  api.listPatients.mockResolvedValue([{ patient_id: "p1", name: "Pat One", reference: "", documents: [{ document_id: "d1" }] }]);
  api.authChecklist.mockResolvedValue({ items: [
    { item_id: "proc-1", category: "procedure", description: "CPT code", required: true, source: "suggested", completed: false }],
    citations: [], missing_count: 1 });
  api.saveChecklist.mockResolvedValue({});
  render(<PriorAuth />);
  await waitFor(() => expect(screen.getByLabelText("Patient")).toHaveValue("p1"));
  await waitFor(() => expect(screen.getByLabelText("Policy")).toHaveValue("d1"));
  await userEvent.type(screen.getByPlaceholderText(/Knee MRI/), "MRI");
  await userEvent.click(screen.getByRole("button", { name: /Generate/ }));
  await userEvent.click(await screen.findByRole("button", { name: "Save to patient record" }));
  expect(api.saveChecklist).toHaveBeenCalledWith("p1", {
    document_id: "d1", service_name: "MRI", service_code: "", diagnosis_code: "",
    items: [{ item_id: "proc-1", category: "procedure", description: "CPT code", required: true, completed: false }],
  });
  expect(await screen.findByRole("status")).toHaveTextContent("Saved to Pat One's record");
});
