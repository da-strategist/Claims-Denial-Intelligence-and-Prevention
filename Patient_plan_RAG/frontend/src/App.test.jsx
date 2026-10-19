import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { api, AUTH_REQUIRED_EVENT } from "./services/api";

vi.mock("./services/api", () => ({
  AUTH_REQUIRED_EVENT: "auth-required",
  api: { me: vi.fn(), login: vi.fn(), logout: vi.fn(), changePassword: vi.fn() },
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

const MEMBER = { username: "m@example.com", role: "member", plan_ids: [], must_change_password: false };
const ADMIN = { ...MEMBER, username: "a@example.com", role: "admin" };

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
  renderApp();
  expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong on this page");
  expect(screen.getByText(/Demonstration Only/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Ask a Question/ })).toBeInTheDocument();
});

test("navigating away from a crashed page recovers", async () => {
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

test("only admins get the Admin page", async () => {
  window.location.hash = "/admin";
  const { unmount } = renderApp();
  expect(await screen.findByRole("alert")).toHaveTextContent("Not permitted");
  expect(screen.queryByRole("button", { name: /Admin/ })).toBeNull();
  unmount();

  api.me.mockResolvedValue(ADMIN);
  renderApp();
  expect(await screen.findByText("admin page")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Admin/ })).toBeInTheDocument();
});
