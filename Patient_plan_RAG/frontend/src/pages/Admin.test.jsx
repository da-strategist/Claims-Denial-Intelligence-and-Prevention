import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Admin from "./Admin";
import { api } from "../services/api";

vi.mock("../services/api", () => ({
  api: {
    listOrgs: vi.fn(), createOrg: vi.fn(), updateOrg: vi.fn(), approveOrg: vi.fn(), rejectOrg: vi.fn(),
    listUsers: vi.fn(), updateUser: vi.fn(), resetPassword: vi.fn(),
    userDetail: vi.fn(), deleteUser: vi.fn(), orgDetail: vi.fn(), deleteOrg: vi.fn(),
  },
}));
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: { username: "admin@example.com", role: "platform_admin" } }),
}));

const ORGS = [
  { org_id: "org3", name: "Lakeside Clinic", category: "clinic", status: "pending", npi: "1234567893",
    city: "Riverton", address: "2 Lake Rd", phone: "555 0101", signed_up_by: "dana@lakeside.example",
    signed_up_by_name: "Dana Lee", created_at: "2026-10-21T09:00:00+00:00", staff_count: 1,
    patient_count: 0, disabled: false },
  { org_id: "org1", name: "General Hospital", category: "hospital", status: "active", city: "Springfield",
    staff_count: 2, patient_count: 5, disabled: false },
  { org_id: "org2", name: "Fake Care", category: "other", status: "rejected", review_note: "No such provider",
    city: "", staff_count: 1, patient_count: 0, disabled: false },
];
const USERS = [
  { username: "admin@example.com", role: "platform_admin", org_id: null, org_name: null,
    must_change_password: false, disabled: false },
  { username: "ga@general.example", role: "hospital_admin", org_id: "org1", org_name: "General Hospital",
    must_change_password: true, disabled: false },
  { username: "alice@example.com", role: "individual", org_id: null, org_name: null, full_name: "Alice Smith",
    must_change_password: false, disabled: false, last_sign_in: "2026-10-21T09:00:00+00:00" },
];

beforeEach(() => {
  api.listOrgs.mockResolvedValue(ORGS);
  api.listUsers.mockResolvedValue(USERS);
});
afterEach(() => vi.clearAllMocks());

const row = (text) => screen.getByText(text).closest("tr");

test("lists providers with category and counts, and accounts with their type", async () => {
  render(<Admin />);
  expect(await screen.findByText("ga@general.example")).toBeInTheDocument();
  expect(within(row("alice@example.com")).getByText("Individual")).toBeInTheDocument();
  expect(within(row("ga@general.example")).getByText("Awaiting first sign-in")).toBeInTheDocument();
  const hospitalRow = screen.getAllByText("General Hospital").map((el) => el.closest("tr"))
    .find((tr) => within(tr).queryByText("5"));
  expect(within(hospitalRow).getByText("Hospital")).toBeInTheDocument();
  expect(within(hospitalRow).getByText("Active")).toBeInTheDocument();
  expect(within(row("Fake Care")).getByText("Rejected")).toBeInTheDocument();
  expect(within(row("Fake Care")).getByText("No such provider")).toBeInTheDocument();
});

test("pending sign-ups are listed for review with their details", async () => {
  render(<Admin />);
  const queue = (await screen.findByRole("heading", { name: "Waiting for approval (1)" })).closest("section");
  for (const text of ["Lakeside Clinic", "Clinic or physician practice", "1234567893",
                      "2 Lake Rd, Riverton", "Dana Lee dana@lakeside.example", "Signed up 2026-10-21"])
    expect(within(queue).getByText(text)).toBeInTheDocument();
  // pending providers are not in the providers table
  expect(screen.queryAllByText("Lakeside Clinic").filter((el) => el.closest("tr"))).toEqual([]);
});

test("approving and rejecting a sign-up, with a note", async () => {
  api.approveOrg.mockResolvedValue({});
  api.rejectOrg.mockResolvedValue({});
  render(<Admin />);
  await screen.findByText("Lakeside Clinic");
  await userEvent.type(screen.getByLabelText("Note for Lakeside Clinic"), " NPI checked ");
  await userEvent.click(screen.getByRole("button", { name: "Approve" }));
  expect(api.approveOrg).toHaveBeenCalledWith("org3", "NPI checked");
  await waitFor(() => expect(api.listOrgs).toHaveBeenCalledTimes(2));
  await userEvent.click(screen.getByRole("button", { name: "Reject" }));
  expect(api.rejectOrg).toHaveBeenCalledWith("org3", "NPI checked");
  await userEvent.click(within(row("Fake Care")).getByRole("button", { name: "Approve after all" }));
  expect(api.approveOrg).toHaveBeenLastCalledWith("org2");
});

test("nothing waiting", async () => {
  api.listOrgs.mockResolvedValue(ORGS.filter((o) => o.status !== "pending"));
  render(<Admin />);
  expect(await screen.findByText("No provider sign-ups are waiting.")).toBeInTheDocument();
});

test("adding a provider directly shows its admin's temporary password once", async () => {
  api.createOrg.mockResolvedValue({ org_id: "org2", admin_username: "boss@new.example",
                                    temporary_password: "Temp-Pass-123" });
  render(<Admin />);
  await screen.findByText("alice@example.com");
  await userEvent.type(screen.getByLabelText("Provider name"), "Main St Pharmacy");
  await userEvent.type(screen.getByLabelText("Provider admin email"), "boss@new.example");
  await userEvent.selectOptions(screen.getByLabelText("Category"), "pharmacy");
  await userEvent.type(screen.getByLabelText("City"), "Riverton");
  await userEvent.click(screen.getByRole("button", { name: "Add provider" }));
  expect(api.createOrg).toHaveBeenCalledWith({ name: "Main St Pharmacy", adminUsername: "boss@new.example",
                                               category: "pharmacy", city: "Riverton" });
  const notice = await screen.findByRole("status");
  expect(notice).toHaveTextContent("boss@new.example");
  expect(notice).toHaveTextContent("Temp-Pass-123");
  await userEvent.click(within(notice).getByRole("button", { name: "Done" }));
  expect(screen.queryByText("Temp-Pass-123")).toBeNull();
});

test("disabling a provider, resetting and disabling accounts", async () => {
  api.updateOrg.mockResolvedValue({});
  api.updateUser.mockResolvedValue({});
  api.resetPassword.mockResolvedValue({ username: "alice@example.com", temporary_password: "Reset-456" });
  render(<Admin />);
  await screen.findByText("alice@example.com");
  const hospitalRow = screen.getAllByText("General Hospital").map((el) => el.closest("tr"))
    .find((tr) => within(tr).queryByText("5"));
  await userEvent.click(within(hospitalRow).getByRole("button", { name: "Disable" }));
  expect(api.updateOrg).toHaveBeenCalledWith("org1", { disabled: true });
  await userEvent.click(within(row("alice@example.com")).getByRole("button", { name: "Reset password" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Reset-456");
  await userEvent.click(within(row("alice@example.com")).getByRole("button", { name: "Disable" }));
  await waitFor(() => expect(api.updateUser).toHaveBeenCalledWith("alice@example.com", { disabled: true }));
});

test("the platform admin cannot disable their own account", async () => {
  render(<Admin />);
  await screen.findByText("alice@example.com");
  expect(within(row("admin@example.com")).queryByRole("button", { name: "Disable" })).toBeNull();
});

test("errors from the server are shown", async () => {
  api.createOrg.mockRejectedValue(new Error("400: An account for alice@example.com already exists."));
  render(<Admin />);
  await screen.findByText("alice@example.com");
  await userEvent.type(screen.getByLabelText("Provider name"), "Dup");
  await userEvent.type(screen.getByLabelText("Provider admin email"), "alice@example.com");
  await userEvent.click(screen.getByRole("button", { name: "Add provider" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("already exists");
});

test("accounts can be searched and filtered", async () => {
  render(<Admin />);
  await screen.findByText("alice@example.com");
  await userEvent.type(screen.getByLabelText("Search accounts"), "smith");
  expect(screen.getByText("alice@example.com")).toBeInTheDocument();
  expect(screen.queryByText("ga@general.example")).toBeNull();
  await userEvent.clear(screen.getByLabelText("Search accounts"));
  await userEvent.selectOptions(screen.getByLabelText("Account status"), "first");
  expect(screen.getByText("ga@general.example")).toBeInTheDocument();
  expect(screen.queryByText("alice@example.com")).toBeNull();
  await userEvent.selectOptions(screen.getByLabelText("Account type"), "individual");
  expect(screen.getByText("No accounts match.")).toBeInTheDocument();
});

test("account detail shows counts, and a spam individual can be deleted with the exact email", async () => {
  api.userDetail.mockResolvedValue({ ...USERS[2], created_at: "2026-10-01T00:00:00+00:00",
                                     holds: { policies: 2, shares: 1, providers: 3, connected_providers: 1 } });
  api.deleteUser.mockResolvedValue({});
  render(<Admin />);
  await userEvent.click(await screen.findByRole("button", { name: "alice@example.com" }));
  const panel = await screen.findByRole("region", { name: "Account alice@example.com" });
  expect(within(panel).getByText("3 (1 on the platform)")).toBeInTheDocument();
  expect(within(panel).getByText(/Counts only/)).toBeInTheDocument();
  await userEvent.click(within(panel).getByRole("button", { name: "Delete account (spam)" }));
  const del = within(panel).getByRole("button", { name: "Delete" });
  expect(del).toBeDisabled();
  await userEvent.type(within(panel).getByLabelText("Type to confirm"), "alice@example.com");
  await userEvent.click(del);
  expect(api.deleteUser).toHaveBeenCalledWith("alice@example.com", "alice@example.com");
});

test("provider staff accounts have no delete button", async () => {
  api.userDetail.mockResolvedValue({ ...USERS[1] });
  render(<Admin />);
  await userEvent.click(await screen.findByRole("button", { name: "ga@general.example" }));
  const panel = await screen.findByRole("region", { name: "Account ga@general.example" });
  expect(within(panel).queryByRole("button", { name: /Delete/ })).toBeNull();
});

test("provider details are view-only; a rejected sign-up can be deleted", async () => {
  api.orgDetail.mockResolvedValue({ ...ORGS[2], category_label: "Other provider", npi: "", staff: [
    { username: "f@fake.example", role: "hospital_admin", full_name: "F", last_sign_in: "", disabled: false }],
    connection_count: 0, share_count: 0, reviewed_by: "admin@example.com", reviewed_at: "2026-10-21T10:00:00+00:00" });
  api.deleteOrg.mockResolvedValue({});
  render(<Admin />);
  await userEvent.click(await screen.findByRole("button", { name: "Fake Care" }));
  const panel = await screen.findByRole("region", { name: "Provider Fake Care" });
  expect(within(panel).getByText(/Changes are made by the provider's admin/)).toBeInTheDocument();
  expect(within(panel).queryByRole("textbox", { name: /name|city|address/i })).toBeNull();
  expect(within(panel).getByText(/f@fake.example/)).toBeInTheDocument();
  await userEvent.click(within(panel).getByRole("button", { name: "Delete rejected sign-up" }));
  await userEvent.type(within(panel).getByLabelText("Type to confirm"), "Fake Care");
  await userEvent.click(within(panel).getByRole("button", { name: "Delete" }));
  expect(api.deleteOrg).toHaveBeenCalledWith("org2", "Fake Care");
});

test("approved providers have no delete button", async () => {
  api.orgDetail.mockResolvedValue({ ...ORGS[1], category_label: "Hospital", staff: [], connection_count: 2, share_count: 3 });
  render(<Admin />);
  await userEvent.click(await screen.findByRole("button", { name: "General Hospital" }));
  const panel = await screen.findByRole("region", { name: "Provider General Hospital" });
  expect(within(panel).queryByRole("button", { name: /Delete/ })).toBeNull();
});
