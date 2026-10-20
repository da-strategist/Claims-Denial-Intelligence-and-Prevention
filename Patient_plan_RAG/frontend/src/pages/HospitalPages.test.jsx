import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Patients from "./Patients";
import SharedWithUs from "./SharedWithUs";
import Staff from "./Staff";
import { api } from "../services/api";

vi.mock("../services/api", () => ({
  api: {
    listPatients: vi.fn(), createPatient: vi.fn(), getPatient: vi.fn(), uploadPolicy: vi.fn(),
    listShared: vi.fn(), fileShared: vi.fn(),
    listStaff: vi.fn(), addStaff: vi.fn(), updateStaff: vi.fn(), resetStaffPassword: vi.fn(),
  },
}));
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: { username: "ha@h.example", role: "hospital_admin", org_id: "org1" } }),
}));

const P1 = { patient_id: "p1", name: "Pat One", reference: "MRN-1", date_of_birth: "1980-02-03",
             documents: [{ document_id: "d1", filename: "p1.pdf", plan_name: "Silver HMO" }] };
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
  await userEvent.click(screen.getByRole("button", { name: "Ask about this patient's coverage" }));
  expect(window.location.hash).toBe("#/chat?patient=p1");
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
