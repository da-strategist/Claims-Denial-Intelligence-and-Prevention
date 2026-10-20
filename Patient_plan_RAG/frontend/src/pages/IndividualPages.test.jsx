import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MyAccount from "./MyAccount";
import SharingAccess from "./SharingAccess";
import Settings from "./Settings";
import { api } from "../services/api";

vi.mock("../services/api", () => ({
  api: {
    overview: vi.fn(), addProvider: vi.fn(), updateProvider: vi.fn(), deleteProvider: vi.fn(),
    sharingOverview: vi.fn(), hospitalDirectory: vi.fn(), listPolicies: vi.fn(), share: vi.fn(),
    unshare: vi.fn(), removeHospitalAccess: vi.fn(),
    updateProfile: vi.fn(), signOutEverywhere: vi.fn(), exportMyData: vi.fn(), deleteAccount: vi.fn(),
  },
}));
const auth = { refresh: vi.fn(), signOut: vi.fn() };
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { username: "alice@example.com", role: "individual", full_name: "", phone: "" },
    ...auth,
  }),
}));

const OVERVIEW = {
  profile: { username: "alice@example.com", full_name: "Alice Smith", phone: "555 0100" },
  insurance: [
    { insurer: "Apex Health Insurance", plans: [{ document_id: "d1", name: "Gold PPO Plan",
      plan_id: "AHI-1", effective_date: "2025-01-01", expiration_date: "2025-12-31", expired: true }] },
    { insurer: "Summit Care", plans: [{ document_id: "d2", name: "Silver HMO", plan_id: "",
      effective_date: null, expiration_date: null, expired: false }] },
  ],
  providers: [{ provider_id: "p1", name: "Dr. Lee", kind: "doctor", phone: "555 0101", notes: "GP" }],
  sharing: [{ org_id: "o1", org_name: "General Hospital", policies: [{ share_id: "s1", document_id: "d1", name: "Gold PPO Plan" }] }],
  policy_count: 2,
};

beforeEach(() => {
  api.overview.mockResolvedValue(OVERVIEW);
  api.sharingOverview.mockResolvedValue(OVERVIEW.sharing);
  api.hospitalDirectory.mockResolvedValue([{ org_id: "o1", name: "General Hospital" }, { org_id: "o2", name: "Mercy" }]);
  api.listPolicies.mockResolvedValue([
    { document_id: "d1", filename: "a.pdf", plan_name: "Gold PPO Plan", owner: "alice@example.com" },
    { document_id: "s9", filename: "sample.pdf", plan_name: "Sample", owner: null },
  ]);
  for (const fn of Object.values(api)) if (!fn.getMockImplementation()) fn.mockResolvedValue({});
});
afterEach(() => vi.clearAllMocks());

// ── My account ───────────────────────────────────────────────────────

test("my account shows profile, insurance by company, providers and sharing", async () => {
  render(<MyAccount />);
  expect(await screen.findByRole("heading", { name: "Hello, Alice Smith" })).toBeInTheDocument();
  expect(screen.getByText("Apex Health Insurance")).toBeInTheDocument();
  expect(screen.getByText("Summit Care")).toBeInTheDocument();
  expect(screen.getByText("Ended")).toBeInTheDocument();
  expect(screen.getByText("Dr. Lee")).toBeInTheDocument();
  expect(screen.getByText(/1 hospital can see some of your policies: General Hospital/)).toBeInTheDocument();
});

test("adding and removing a provider", async () => {
  render(<MyAccount />);
  await screen.findByText("Dr. Lee");
  await userEvent.click(screen.getByRole("button", { name: "+ Add a provider" }));
  await userEvent.type(screen.getByLabelText("Provider name"), "City Pharmacy");
  await userEvent.selectOptions(screen.getByLabelText("Provider type"), "pharmacy");
  await userEvent.click(screen.getByRole("button", { name: "Add provider" }));
  expect(api.addProvider).toHaveBeenCalledWith({ name: "City Pharmacy", kind: "pharmacy", phone: "", notes: "" });
  await userEvent.click(screen.getByRole("button", { name: "Remove" }));
  expect(api.deleteProvider).toHaveBeenCalledWith("p1");
});

test("a new account is prompted to upload a policy", async () => {
  api.overview.mockResolvedValue({ ...OVERVIEW, insurance: [], providers: [], sharing: [], policy_count: 0,
                                   profile: { username: "alice@example.com", full_name: "", phone: "" } });
  render(<MyAccount />);
  expect(await screen.findByRole("button", { name: "Upload your insurance policy" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Ask about my coverage" })).toBeDisabled();
  expect(screen.getByText(/Only you/)).toBeInTheDocument();
});

// ── Sharing & access ─────────────────────────────────────────────────

test("sharing page: share, stop sharing, remove a hospital", async () => {
  render(<SharingAccess />);
  expect(await screen.findByText("General Hospital", { selector: "strong" })).toBeInTheDocument();
  const policyOptions = [...screen.getByLabelText("Policy to share").options].map((o) => o.textContent);
  expect(policyOptions).toEqual(["Choose a policy…", "Gold PPO Plan"]);  // samples can't be shared
  await userEvent.selectOptions(screen.getByLabelText("Policy to share"), "d1");
  await userEvent.selectOptions(screen.getByLabelText("Hospital to share with"), "o2");
  await userEvent.click(screen.getByRole("button", { name: "Share" }));
  expect(api.share).toHaveBeenCalledWith("d1", "o2");
  await userEvent.click(screen.getByRole("button", { name: "Stop sharing" }));
  expect(api.unshare).toHaveBeenCalledWith("s1");
  await userEvent.click(screen.getByRole("button", { name: "Remove all access" }));
  expect(api.removeHospitalAccess).toHaveBeenCalledWith("o1");
  expect(screen.getByText(/hospital's records/)).toBeInTheDocument();
});

// ── Settings ─────────────────────────────────────────────────────────

test("settings: save profile and sign out everywhere", async () => {
  render(<Settings />);
  await userEvent.type(screen.getByLabelText("Full name"), "Alice Smith");
  await userEvent.click(screen.getByRole("button", { name: "Save profile" }));
  expect(api.updateProfile).toHaveBeenCalledWith("Alice Smith", "");
  await waitFor(() => expect(auth.refresh).toHaveBeenCalled());
  expect(await screen.findByRole("status")).toHaveTextContent("Profile saved");
  await userEvent.click(screen.getByRole("button", { name: "Sign out on all devices" }));
  expect(api.signOutEverywhere).toHaveBeenCalled();
  await waitFor(() => expect(auth.signOut).toHaveBeenCalled());
});

test("deleting the account needs the exact email", async () => {
  render(<Settings />);
  await userEvent.click(screen.getByRole("button", { name: "Delete my account…" }));
  const button = screen.getByRole("button", { name: "Permanently delete my account" });
  await userEvent.type(screen.getByLabelText(/Type your email/), "alice@example.co");
  expect(button).toBeDisabled();
  await userEvent.type(screen.getByLabelText(/Type your email/), "m");
  expect(button).toBeEnabled();
  await userEvent.click(button);
  expect(api.deleteAccount).toHaveBeenCalledWith("alice@example.com");
  await waitFor(() => expect(auth.signOut).toHaveBeenCalled());
});

test("download my data saves a JSON file", async () => {
  api.exportMyData.mockResolvedValue({ profile: { username: "alice@example.com" } });
  URL.createObjectURL = vi.fn(() => "blob:x");
  URL.revokeObjectURL = vi.fn();
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<Settings />);
  await userEvent.click(screen.getByRole("button", { name: "Download my data" }));
  await waitFor(() => expect(click).toHaveBeenCalled());
  expect(screen.getByRole("status")).toHaveTextContent("downloaded");
});
