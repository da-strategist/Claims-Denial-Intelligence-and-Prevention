import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PolicyViewer from "./PolicyViewer";
import { api } from "../services/api";

vi.mock("../services/api", () => ({
  api: {
    listPolicies: vi.fn(), getPolicy: vi.fn(), getPolicySummary: vi.fn(), getPolicyChunks: vi.fn(),
    uploadPolicy: vi.fn(), hospitalDirectory: vi.fn(), myShares: vi.fn(), share: vi.fn(), unshare: vi.fn(),
    renamePolicy: vi.fn(), deletePolicy: vi.fn(), sampleHealth: vi.fn(), reprocessSample: vi.fn(),
  },
}));
let mockUser = { username: "alice@example.com", role: "individual" };
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ user: mockUser }) }));

const MINE = { document_id: "d1", filename: "alice.pdf", plan_name: "Gold PPO", owner: "alice@example.com",
               org_id: null, page_count: 6, chunk_count: 21, status: "completed" };
const SAMPLE = { ...MINE, document_id: "s1", plan_name: "Silver HMO", owner: null };

beforeEach(() => {
  mockUser = { username: "alice@example.com", role: "individual" };
  window.location.hash = "/policies";
  api.listPolicies.mockResolvedValue([MINE, SAMPLE]);
  api.getPolicySummary.mockResolvedValue(null);
});
afterEach(() => vi.clearAllMocks());

test("individuals see their own and sample policies, labelled", async () => {
  render(<PolicyViewer />);
  expect(await screen.findByRole("heading", { name: "My policies" })).toBeInTheDocument();
  expect(screen.getByText("Yours")).toBeInTheDocument();
  expect(screen.getByText("Sample")).toBeInTheDocument();
  expect(screen.getByText(/unless you share them with a provider/)).toBeInTheDocument();
});

test("individuals share their own policy with a hospital and can stop sharing", async () => {
  window.location.hash = "/policies/d1";
  api.getPolicy.mockResolvedValue(MINE);
  api.hospitalDirectory.mockResolvedValue([{ org_id: "o1", name: "General Hospital" },
                                           { org_id: "o2", name: "Mercy Medical" }]);
  api.myShares.mockResolvedValueOnce([])
    .mockResolvedValue([{ share_id: "sh1", document_id: "d1", org_id: "o1", org_name: "General Hospital" }]);
  api.share.mockResolvedValue({});
  api.unshare.mockResolvedValue({});
  render(<PolicyViewer />);
  await userEvent.selectOptions(await screen.findByLabelText("Provider"), "o1");
  await userEvent.click(screen.getByRole("button", { name: "Share" }));
  expect(api.share).toHaveBeenCalledWith("d1", "o1");
  expect(await screen.findByText("General Hospital")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Stop sharing" }));
  expect(api.unshare).toHaveBeenCalledWith("sh1");
});

test("no share panel on samples", async () => {
  window.location.hash = "/policies/s1";
  api.getPolicy.mockResolvedValue(SAMPLE);
  render(<PolicyViewer />);
  await screen.findByRole("heading", { name: /Silver HMO/ });
  expect(screen.queryByText("Share with a hospital")).toBeNull();
});

test("hospital staff upload from the patient page, not here", async () => {
  mockUser = { username: "s@h.example", role: "hospital_staff", org_id: "o1" };
  render(<PolicyViewer />);
  expect(await screen.findByText(/from their page under Patients/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Upload/ })).toBeNull();
});

test("platform admin uploads samples, with a warning", async () => {
  mockUser = { username: "admin@example.com", role: "platform_admin" };
  api.sampleHealth.mockResolvedValue([]);
  render(<PolicyViewer />);
  expect(await screen.findByRole("heading", { name: "Sample policies" })).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText(/Never upload real member documents/)).toBeInTheDocument());
});

test("platform admin sees sample health and can re-process a sample", async () => {
  mockUser = { username: "admin@example.com", role: "platform_admin" };
  const base = { document_id: "s1", filename: "apex.pdf", name: "Gold PPO", page_count: 12, chunk_count: 40,
                 current_chunker_version: 3, metadata_found: ["insurer_name", "plan_name"],
                 metadata_missing: ["plan_id"] };
  api.sampleHealth.mockResolvedValue([
    { ...base, chunker_version: 2, healthy: false, problems: ["built with an older chunker"] },
  ]);
  api.reprocessSample.mockResolvedValue({});
  render(<PolicyViewer />);
  expect(await screen.findByText("built with an older chunker")).toBeInTheDocument();
  expect(screen.getByText("v2 (current v3)")).toBeInTheDocument();
  expect(screen.getByText("missing: plan id")).toBeInTheDocument();
  api.sampleHealth.mockResolvedValue([{ ...base, chunker_version: 3, healthy: true, problems: [] }]);
  await userEvent.click(screen.getByRole("button", { name: "Re-process Gold PPO" }));
  expect(api.reprocessSample).toHaveBeenCalledWith("s1");
  expect(await screen.findByText("Healthy")).toBeInTheDocument();
});


test("owners can rename and delete their policy", async () => {
  window.location.hash = "/policies/d1";
  api.getPolicy.mockResolvedValue(MINE);
  api.hospitalDirectory.mockResolvedValue([]);
  api.myShares.mockResolvedValue([]);
  api.renamePolicy.mockResolvedValue({ ...MINE, display_name: "Work plan" });
  api.deletePolicy.mockResolvedValue({});
  render(<PolicyViewer />);
  await userEvent.click(await screen.findByRole("button", { name: "Rename" }));
  await userEvent.type(screen.getByLabelText("Policy name"), "Work plan");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(api.renamePolicy).toHaveBeenCalledWith("d1", "Work plan");
  expect(await screen.findByRole("heading", { name: /Work plan/ })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Delete" }));
  expect(screen.getByText(/stop sharing it with every provider/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Delete" }));
  expect(api.deletePolicy).toHaveBeenCalledWith("d1");
  await waitFor(() => expect(window.location.hash).toBe("#/policies"));
});

test("hospital staff can read a shared policy but not change it", async () => {
  mockUser = { username: "s@h.example", role: "hospital_staff", org_id: "o1" };
  window.location.hash = "/policies/d1";
  api.getPolicy.mockResolvedValue(MINE);  // owned by alice, shared with the hospital
  render(<PolicyViewer />);
  await screen.findByRole("heading", { name: /Gold PPO/ });
  expect(screen.queryByRole("button", { name: "Rename" })).toBeNull();
  expect(screen.queryByText("Share with a hospital")).toBeNull();
});
