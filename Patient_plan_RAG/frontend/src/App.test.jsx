import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { api, AUTH_REQUIRED_EVENT } from "./services/api";

vi.mock("./services/api", () => ({
  AUTH_REQUIRED_EVENT: "auth-required",
  api: { me: vi.fn(), login: vi.fn(), register: vi.fn(), logout: vi.fn(), changePassword: vi.fn() },
}));

// Stub pages so no data calls run; Dashboard crashes on render.
vi.mock("./pages/Dashboard", () => ({
  default: () => {
    throw new Error("dashboard exploded");
  },
}));
vi.mock("./pages/ChatAssistant", () => ({ default: () => <p>chat page</p> }));
vi.mock("./pages/PolicyViewer", () => ({ default: () => <p>policies page</p> }));
vi.mock("./pages/CoverageAssessment", () => ({ default: () => <p>coverage page</p> }));
vi.mock("./pages/PriorAuth", () => ({ default: () => <p>auth page</p> }));
vi.mock("./pages/Admin", () => ({ default: () => <p>admin page</p> }));
vi.mock("./pages/Patients", () => ({ default: () => <p>patients page</p> }));
vi.mock("./pages/SharedWithUs", () => ({ default: () => <p>shared page</p> }));
vi.mock("./pages/HospitalOverview", () => ({ default: () => <p>hospital overview page</p> }));
vi.mock("./pages/HospitalAdmin", () => ({ default: () => <p>hospital admin page</p> }));
vi.mock("./pages/MyAccount", () => ({ default: () => <p>my account page</p> }));
vi.mock("./pages/SharingAccess", () => ({ default: () => <p>sharing page</p> }));
vi.mock("./pages/Settings", () => ({ default: () => <p>settings page</p> }));

const MEMBER = { username: "m@example.com", role: "individual", org_id: null, must_change_password: false };
const ADMIN = { ...MEMBER, username: "a@example.com", role: "platform_admin" };
const STAFF = { ...MEMBER, username: "s@h.example", role: "hospital_staff", org_id: "org1" };
const HADMIN = { ...STAFF, username: "ha@h.example", role: "hospital_admin" };

const navLabels = () => within(screen.getByRole("navigation")).getAllByRole("button")
  .map((b) => b.textContent.replace(/^\S+\s/, ""));

function goTo(path) {
  act(() => {
    window.location.hash = path;
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
}

function renderApp() {
  return render(<AuthProvider><App /></AuthProvider>);
}

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  window.location.hash = "/";
  api.me.mockResolvedValue(MEMBER);
  api.logout.mockResolvedValue({});
});
afterEach(() => vi.restoreAllMocks());

// ── Error boundary (signed in) ───────────────────────────────────────

test("a crashing page keeps the disclaimer and navigation on screen", async () => {
  api.me.mockResolvedValue(ADMIN);  // the admin lands on the (crashing) Dashboard
  renderApp();
  expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong on this page");
  expect(screen.getByText(/Demonstration Only/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Ask a Question/ })).toBeInTheDocument();
});

test("navigating away from a crashed page recovers", async () => {
  api.me.mockResolvedValue(ADMIN);  // the admin lands on the (crashing) Dashboard
  renderApp();
  await screen.findByRole("alert");
  goTo("/chat");
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.getByText("chat page")).toBeInTheDocument();
});

test("other pages render normally", async () => {
  window.location.hash = "/coverage";
  renderApp();
  expect(await screen.findByText("coverage page")).toBeInTheDocument();
});

// ── Sign-in ──────────────────────────────────────────────────────────

test("signed-out visitors see only the sign-in page, with the disclaimer", async () => {
  api.me.mockRejectedValue(new Error("401: Sign in required"));
  renderApp();
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  expect(screen.getByText(/Demonstration Only/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Ask a Question/ })).toBeNull();
});

test("signing in shows the app; a wrong password shows the error", async () => {
  api.me.mockRejectedValue(new Error("401: Sign in required"));
  api.login
    .mockRejectedValueOnce(new Error("401: Incorrect email or password"))
    .mockResolvedValueOnce(MEMBER);
  window.location.hash = "/chat";
  renderApp();
  await userEvent.type(await screen.findByLabelText("Email"), "m@example.com");
  await userEvent.type(screen.getByLabelText("Password"), "wrong");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password");
  await userEvent.type(screen.getByLabelText("Password"), "right password");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByText("chat page")).toBeInTheDocument();
  expect(api.login).toHaveBeenLastCalledWith("m@example.com", "right password");
});

test("a temporary password forces a password change first", async () => {
  api.me.mockResolvedValue({ ...MEMBER, must_change_password: true });
  api.changePassword.mockResolvedValue(MEMBER);
  window.location.hash = "/chat";
  renderApp();
  expect(await screen.findByRole("heading", { name: "Choose a new password" })).toBeInTheDocument();
  expect(screen.queryByText("chat page")).toBeNull();
  await userEvent.type(screen.getByLabelText("Temporary password"), "temp-password-1");
  await userEvent.type(screen.getByLabelText(/New password/), "my new passphrase");
  await userEvent.type(screen.getByLabelText("Confirm new password"), "my new passphrase");
  await userEvent.click(screen.getByRole("button", { name: "Save password" }));
  expect(await screen.findByText("chat page")).toBeInTheDocument();
});

test("password change checks length and confirmation before calling the API", async () => {
  api.me.mockResolvedValue({ ...MEMBER, must_change_password: true });
  renderApp();
  await userEvent.type(await screen.findByLabelText("Temporary password"), "temp");
  await userEvent.type(screen.getByLabelText(/New password/), "short");
  await userEvent.type(screen.getByLabelText("Confirm new password"), "short");
  await userEvent.click(screen.getByRole("button", { name: "Save password" }));
  expect(screen.getByRole("alert")).toHaveTextContent("at least 12");
  expect(api.changePassword).not.toHaveBeenCalled();
});

test("an expired session (any 401) returns to sign-in", async () => {
  window.location.hash = "/chat";
  renderApp();
  await screen.findByText("chat page");
  act(() => window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT)));
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});

test("sign out returns to the sign-in page", async () => {
  window.location.hash = "/chat";
  renderApp();
  await screen.findByText("chat page");
  expect(screen.getByText("m@example.com")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  expect(api.logout).toHaveBeenCalled();
});

// ── Roles ────────────────────────────────────────────────────────────

test("each kind of account gets its own navigation", async () => {
  const cases = [
    [MEMBER, ["My Account", "My Policies", "Ask a Question", "Coverage Check", "Sharing & Access", "Settings"]],
    [STAFF, ["Overview", "Patients", "Shared with us", "Ask a Question", "Coverage Check", "Prior Auth"]],
    [HADMIN, ["Overview", "Patients", "Shared with us", "Ask a Question", "Coverage Check", "Prior Auth", "Hospital admin"]],
    [ADMIN, ["Dashboard", "Hospitals & Accounts", "Sample Policies", "Ask a Question"]],
  ];
  for (const [user, expected] of cases) {
    api.me.mockResolvedValue(user);
    window.location.hash = "/chat";
    const { unmount } = renderApp();
    await screen.findByText("chat page");
    expect(navLabels()).toEqual(expected);
    unmount();
  }
});

test("hospital accounts start on their overview", async () => {
  api.me.mockResolvedValue(STAFF);
  renderApp();
  expect(await screen.findByText("hospital overview page")).toBeInTheDocument();
});

test("pages outside your role are refused", async () => {
  for (const [user, path] of [[MEMBER, "/admin"], [MEMBER, "/patients"], [MEMBER, "/auth"],
                              [STAFF, "/settings"], [STAFF, "/sharing"], [STAFF, "/hospital-admin"],
                              [ADMIN, "/patients"], [STAFF, "/admin"]]) {
    api.me.mockResolvedValue(user);
    window.location.hash = path;
    const { unmount } = renderApp();
    expect(await screen.findByRole("alert")).toHaveTextContent("Not permitted");
    unmount();
  }
  api.me.mockResolvedValue(ADMIN);
  window.location.hash = "/admin";
  renderApp();
  expect(await screen.findByText("admin page")).toBeInTheDocument();
});

test("individuals can create an account from the sign-in page", async () => {
  api.me.mockRejectedValue(new Error("401: Sign in required"));
  api.register.mockResolvedValue(MEMBER);
  window.location.hash = "/chat";
  renderApp();
  await userEvent.click(await screen.findByRole("button", { name: /Create an account/ }));
  expect(screen.getByRole("heading", { name: "Create your account" })).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Email"), "new@example.com");
  await userEvent.type(screen.getByLabelText("Password"), "short");
  await userEvent.type(screen.getByLabelText("Confirm password"), "short");
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(screen.getByRole("alert")).toHaveTextContent("at least 12");
  expect(api.register).not.toHaveBeenCalled();
  await userEvent.clear(screen.getByLabelText("Password"));
  await userEvent.type(screen.getByLabelText("Password"), "a long passphrase");
  await userEvent.clear(screen.getByLabelText("Confirm password"));
  await userEvent.type(screen.getByLabelText("Confirm password"), "a long passphrase");
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(await screen.findByText("chat page")).toBeInTheDocument();
  expect(api.register).toHaveBeenCalledWith("new@example.com", "a long passphrase");
});


test("individuals land on My Account, not the system dashboard", async () => {
  renderApp();
  expect(await screen.findByText("my account page")).toBeInTheDocument();
});
