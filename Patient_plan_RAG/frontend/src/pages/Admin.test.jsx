import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Admin from "./Admin";
import { api } from "../services/api";

vi.mock("../services/api", () => ({
  api: {
    listOrgs: vi.fn(), createOrg: vi.fn(), updateOrg: vi.fn(),
    listUsers: vi.fn(), updateUser: vi.fn(), resetPassword: vi.fn(),
  },
}));
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: { username: "admin@example.com", role: "platform_admin" } }),
}));

const ORGS = [{ org_id: "org1", name: "General Hospital", staff_count: 2, patient_count: 5, disabled: false }];
const USERS = [
  { username: "admin@example.com", role: "platform_admin", org_id: null, org_name: null,
    must_change_password: false, disabled: false },
  { username: "ga@general.example", role: "hospital_admin", org_id: "org1", org_name: "General Hospital",
    must_change_password: true, disabled: false },
  { username: "alice@example.com", role: "individual", org_id: null, org_name: null,
    must_change_password: false, disabled: false },
];

beforeEach(() => {
  api.listOrgs.mockResolvedValue(ORGS);
  api.listUsers.mockResolvedValue(USERS);
});
afterEach(() => vi.clearAllMocks());

const row = (text) => screen.getByText(text).closest("tr");

test("lists hospitals with counts and accounts with their type", async () => {
  render(<Admin />);
  expect(await screen.findByText("ga@general.example")).toBeInTheDocument();
  expect(within(row("alice@example.com")).getByText("Individual")).toBeInTheDocument();
  expect(within(row("ga@general.example")).getByText("Awaiting first sign-in")).toBeInTheDocument();
  const hospitalRow = screen.getAllByText("General Hospital").map((el) => el.closest("tr"))
    .find((tr) => within(tr).queryByText("5"));
  expect(hospitalRow).toBeTruthy();
});

test("adding a hospital shows its admin's temporary password once", async () => {
  api.createOrg.mockResolvedValue({ org_id: "org2", admin_username: "boss@new.example",
                                    temporary_password: "Temp-Pass-123" });
  render(<Admin />);
  await screen.findByText("alice@example.com");
  await userEvent.type(screen.getByLabelText("Hospital name"), "New Hospital");
  await userEvent.type(screen.getByLabelText("Hospital admin email"), "boss@new.example");
  await userEvent.click(screen.getByRole("button", { name: "Add hospital" }));
  expect(api.createOrg).toHaveBeenCalledWith("New Hospital", "boss@new.example");
  const notice = await screen.findByRole("status");
  expect(notice).toHaveTextContent("boss@new.example");
  expect(notice).toHaveTextContent("Temp-Pass-123");
  await userEvent.click(within(notice).getByRole("button", { name: "Done" }));
  expect(screen.queryByText("Temp-Pass-123")).toBeNull();
});

test("disabling a hospital, resetting and disabling accounts", async () => {
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
  await userEvent.type(screen.getByLabelText("Hospital name"), "Dup");
  await userEvent.type(screen.getByLabelText("Hospital admin email"), "alice@example.com");
  await userEvent.click(screen.getByRole("button", { name: "Add hospital" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("already exists");
});
