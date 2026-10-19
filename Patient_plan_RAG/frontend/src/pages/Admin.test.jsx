import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Admin from "./Admin";
import { api } from "../services/api";

vi.mock("../services/api", () => ({
  api: {
    listUsers: vi.fn(), listPolicies: vi.fn(), createUser: vi.fn(),
    updateUser: vi.fn(), resetPassword: vi.fn(),
  },
}));
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: { username: "admin@example.com", role: "admin" } }),
}));

const USERS = [
  { username: "admin@example.com", role: "admin", plan_ids: [], must_change_password: false, disabled: false },
  { username: "m@example.com", role: "member", plan_ids: ["apex1"], must_change_password: false, disabled: false },
];
const POLICIES = [
  { document_id: "apex1", filename: "apex.pdf", plan_name: "Gold PPO Plan", owner: null },
  { document_id: "sum1", filename: "summit.pdf", plan_name: "Silver HMO Value", owner: null },
  { document_id: "priv1", filename: "mine.pdf", plan_name: "", owner: "m@example.com" },
];

beforeEach(() => {
  api.listUsers.mockResolvedValue(USERS);
  api.listPolicies.mockResolvedValue(POLICIES);
});
afterEach(() => vi.clearAllMocks());

const row = (email) => screen.getByText(email).closest("tr");

test("lists accounts with plan names; private uploads are not assignable", async () => {
  render(<Admin />);
  expect(await screen.findByText("m@example.com")).toBeInTheDocument();
  expect(within(row("m@example.com")).getByText("Gold PPO Plan")).toBeInTheDocument();
  expect(screen.getByLabelText("Silver HMO Value")).toBeInTheDocument(); // create form picker
  expect(screen.queryByLabelText("mine.pdf")).toBeNull();
});

test("creating a member shows the temporary password once", async () => {
  api.createUser.mockResolvedValue({ username: "new@example.com", temporary_password: "Temp-Pass-123" });
  render(<Admin />);
  await screen.findByText("m@example.com");
  await userEvent.type(screen.getByLabelText("Email"), "new@example.com");
  await userEvent.click(screen.getByLabelText("Silver HMO Value"));
  await userEvent.click(screen.getByRole("button", { name: "Create" }));
  expect(api.createUser).toHaveBeenCalledWith("new@example.com", "member", ["sum1"]);
  const notice = await screen.findByRole("status");
  expect(notice).toHaveTextContent("Temp-Pass-123");
  await userEvent.click(within(notice).getByRole("button", { name: "Done" }));
  expect(screen.queryByText("Temp-Pass-123")).toBeNull();
});

test("editing plans, resetting a password, and disabling", async () => {
  api.updateUser.mockResolvedValue({});
  api.resetPassword.mockResolvedValue({ username: "m@example.com", temporary_password: "Reset-456" });
  render(<Admin />);
  await screen.findByText("m@example.com");
  const member = row("m@example.com");
  await userEvent.click(within(member).getByRole("button", { name: "Edit plans" }));
  await userEvent.click(within(member).getByLabelText("Silver HMO Value"));
  await userEvent.click(within(member).getByRole("button", { name: "Save plans" }));
  expect(api.updateUser).toHaveBeenCalledWith("m@example.com", { plan_ids: ["apex1", "sum1"] });

  await userEvent.click(within(row("m@example.com")).getByRole("button", { name: "Reset password" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Reset-456");

  await userEvent.click(within(row("m@example.com")).getByRole("button", { name: "Disable" }));
  await waitFor(() => expect(api.updateUser).toHaveBeenCalledWith("m@example.com", { disabled: true }));
});

test("admins cannot disable their own account from the list", async () => {
  render(<Admin />);
  await screen.findByText("m@example.com");
  expect(within(row("admin@example.com")).queryByRole("button", { name: "Disable" })).toBeNull();
});

test("errors from the server are shown", async () => {
  api.createUser.mockRejectedValue(new Error("400: User new@example.com already exists."));
  render(<Admin />);
  await screen.findByText("m@example.com");
  await userEvent.type(screen.getByLabelText("Email"), "new@example.com");
  await userEvent.click(screen.getByRole("button", { name: "Create" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("already exists");
});
