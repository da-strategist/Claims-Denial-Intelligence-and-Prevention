import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Patients from "./Patients";
import SharedWithUs from "./SharedWithUs";
import Staff from "./Staff";
import { api } from "../services/api";

vi.mock("../services/api", () => ({
  api: {
    listPatients: vi.fn(), createPatient: vi.fn(), getPatient: vi.fn(), uploadPolicy: vi.fn(),
    updatePatient: vi.fn(), deletePatient: vi.fn(), listChecklists: vi.fn(), updateChecklist: vi.fn(),
    deleteChecklist: vi.fn(),
    listShared: vi.fn(), fileShared: vi.fn(),
    listStaff: vi.fn(), addStaff: vi.fn(), updateStaff: vi.fn(), resetStaffPassword: vi.fn(),
  },
}));
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: { username: "ha@h.example", role: "hospital_admin", org_id: "org1" } }),
}));

const P1 = { patient_id: "p1", name: "Pat One", reference: "MRN-1", date_of_birth: "1980-02-03", archived: false,
             documents: [{ document_id: "d1", filename: "p1.pdf", plan_name: "Silver HMO", insurer_name: "Summit Care",
                           plan_id: "SCH-1", effective_date: "2026-01-01", expiration_date: "2026-12-31",
                           coverage_status: "active" }] };
const P2 = { patient_id: "p2", name: "Bea Two", reference: "", date_of_birth: "", documents: [] };

function goTo(path) {
  act(() => {
    window.location.hash = path;
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
}

beforeEach(() => {
  window.location.hash = "/patients";
  api.listPatients.mockResolvedValue([P1, P2]);
  api.listChecklists.mockResolvedValue([]);
});
afterEach(() => vi.clearAllMocks());

// ── Patients ─────────────────────────────────────────────────────────

test("patient list with search", async () => {
  render(<Patients />);
  expect(await screen.findByText("Pat One")).toBeInTheDocument();
  await userEvent.type(screen.getByPlaceholderText("Search by name or MRN"), "mrn-1");
  expect(screen.getByText("Pat One")).toBeInTheDocument();
  expect(screen.queryByText("Bea Two")).toBeNull();
});

test("adding a patient opens their record", async () => {
  api.createPatient.mockResolvedValue({ ...P2, patient_id: "p9", name: "New Person" });
  render(<Patients />);
  await screen.findByText("Pat One");
  await userEvent.type(screen.getByLabelText("Name"), "New Person");
  await userEvent.type(screen.getByLabelText("Hospital number (MRN)"), "MRN-9");
  await userEvent.click(screen.getByRole("button", { name: "Add patient" }));
  expect(api.createPatient).toHaveBeenCalledWith({ name: "New Person", reference: "MRN-9", date_of_birth: "" });
  await waitFor(() => expect(window.location.hash).toBe("#/patients/p9"));
});

test("patient record: documents, upload for this patient, ask link", async () => {
  api.getPatient.mockResolvedValue(P1);
  api.uploadPolicy.mockResolvedValue({});
  window.location.hash = "/patients/p1";
  render(<Patients />);
  expect(await screen.findByRole("heading", { name: "Pat One" })).toBeInTheDocument();
  expect(screen.getByText("Silver HMO")).toBeInTheDocument();
  const file = new File(["%PDF-1.4"], "card.pdf", { type: "application/pdf" });
  await userEvent.upload(screen.getByLabelText("Policy PDF"), file);
  await userEvent.click(screen.getByRole("button", { name: "Upload policy for this patient" }));
  expect(api.uploadPolicy).toHaveBeenCalledWith(file, "p1");
  for (const name of ["Ask about coverage", "Check coverage for a service", "Prior auth checklist"]) {
    expect(screen.getByRole("button", { name })).toBeEnabled();
  }
  await userEvent.click(screen.getByRole("button", { name: "Ask about coverage" }));
  expect(window.location.hash).toBe("#/chat?patient=p1");
});

test.each([
  ["Check coverage for a service", "#/coverage?patient=p1"],
  ["Prior auth checklist", "#/auth?patient=p1"],
])("%s opens that page for this patient", async (name, hash) => {
  api.getPatient.mockResolvedValue(P1);
  window.location.hash = "/patients/p1";
  render(<Patients />);
  await userEvent.click(await screen.findByRole("button", { name }));
  expect(window.location.hash).toBe(hash);
});

test("a patient from another hospital shows an error", async () => {
  api.getPatient.mockRejectedValue(new Error("404: Patient not found"));
  window.location.hash = "/patients/p404";
  render(<Patients />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Patient not found");
});

// ── Shared with us ───────────────────────────────────────────────────

test("shared policies can be filed under a patient", async () => {
  api.listShared.mockResolvedValue([{ share_id: "s1", document_id: "d9", filename: "alice.pdf",
                                      plan_name: "Gold PPO", shared_by: "alice@example.com", patient_id: null }]);
  api.fileShared.mockResolvedValue({});
  render(<SharedWithUs />);
  expect(await screen.findByText("alice@example.com")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Patient for Gold PPO"), "p1");
  expect(api.fileShared).toHaveBeenCalledWith("s1", "p1");
});

test("nothing shared yet", async () => {
  api.listShared.mockResolvedValue([]);
  render(<SharedWithUs />);
  expect(await screen.findByText(/Nothing has been shared/)).toBeInTheDocument();
});

// ── Staff ────────────────────────────────────────────────────────────

test("hospital admin adds staff and sees the temporary password once", async () => {
  api.listStaff.mockResolvedValue([
    { username: "ha@h.example", role: "hospital_admin", must_change_password: false, disabled: false },
    { username: "s@h.example", role: "hospital_staff", must_change_password: false, disabled: false },
  ]);
  api.addStaff.mockResolvedValue({ username: "new@h.example", temporary_password: "Temp-1" });
  api.updateStaff.mockResolvedValue({});
  render(<Staff />);
  await screen.findByText("s@h.example");
  expect(within(screen.getByText("ha@h.example").closest("tr")).queryByRole("button", { name: "Disable" })).toBeNull();
  await userEvent.type(screen.getByLabelText("Email"), "new@h.example");
  await userEvent.click(screen.getByRole("button", { name: "Add staff" }));
  expect(api.addStaff).toHaveBeenCalledWith("new@h.example", "hospital_staff");
  expect(await screen.findByRole("status")).toHaveTextContent("Temp-1");
  await userEvent.click(within(screen.getByText("s@h.example").closest("tr")).getByRole("button", { name: "Disable" }));
  expect(api.updateStaff).toHaveBeenCalledWith("s@h.example", { disabled: true });
});


test("patient record shows the insurance summary with status", async () => {
  api.getPatient.mockResolvedValue({ ...P1, documents: [...P1.documents,
    { document_id: "d2", filename: "old.pdf", plan_name: "Gold PPO", insurer_name: "Apex", plan_id: "",
      effective_date: "2025-01-01", expiration_date: "2025-12-31", coverage_status: "ended" }] });
  window.location.hash = "/patients/p1";
  render(<Patients />);
  expect(await screen.findByText("Summit Care")).toBeInTheDocument();
  expect(screen.getByText("SCH-1")).toBeInTheDocument();
  expect(screen.getByText("active")).toBeInTheDocument();
  expect(screen.getByText("ended")).toBeInTheDocument();
});

test("editing, archiving and deleting a patient", async () => {
  api.getPatient.mockResolvedValue(P1);
  api.updatePatient.mockImplementation(async (id, changes) => ({ ...P1, ...changes }));
  api.deletePatient.mockResolvedValue({});
  window.location.hash = "/patients/p1";
  render(<Patients />);
  await userEvent.click(await screen.findByRole("button", { name: "Edit details" }));
  await userEvent.clear(screen.getByLabelText("Name"));
  await userEvent.type(screen.getByLabelText("Name"), "Pat Onee");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(api.updatePatient).toHaveBeenCalledWith("p1", { name: "Pat Onee", reference: "MRN-1", date_of_birth: "1980-02-03" });
  expect(await screen.findByRole("heading", { name: /Pat Onee/ })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Archive" }));
  expect(api.updatePatient).toHaveBeenLastCalledWith("p1", { archived: true });
  expect(await screen.findByText("Archived")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Delete patient" }));
  expect(screen.getByText(/Policies the\s+patient shared stay theirs/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Delete" }));
  expect(api.deletePatient).toHaveBeenCalledWith("p1");
  await waitFor(() => expect(window.location.hash).toBe("#/patients"));
});

test("saved checklists can be ticked", async () => {
  api.getPatient.mockResolvedValue(P1);
  api.listChecklists.mockResolvedValue([{ checklist_id: "c1", service_name: "MRI", service_code: "70551",
    created_by: "s@h.example", items: [
      { item_id: "proc-1", category: "procedure", description: "CPT code", required: true, completed: false }] }]);
  api.updateChecklist.mockResolvedValue({});
  window.location.hash = "/patients/p1";
  render(<Patients />);
  await userEvent.click(await screen.findByLabelText("CPT code"));
  expect(api.updateChecklist).toHaveBeenCalledWith("p1", "c1", [
    { item_id: "proc-1", category: "procedure", description: "CPT code", required: true, completed: true }]);
});

test("archived patients appear only when asked for", async () => {
  render(<Patients />);
  await screen.findByText("Pat One");
  await userEvent.click(screen.getByLabelText("Show archived"));
  expect(api.listPatients).toHaveBeenLastCalledWith(true);
});
