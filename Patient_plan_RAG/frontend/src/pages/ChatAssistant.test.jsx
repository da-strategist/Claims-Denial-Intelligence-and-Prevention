import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatAssistant from "./ChatAssistant";
import { api } from "../services/api";

vi.mock("../services/api", () => ({
  api: {
    listPolicies: vi.fn(), listPatients: vi.fn(), chat: vi.fn(), health: vi.fn(),
    chatSuggestions: vi.fn(), getPolicySummary: vi.fn(),
  },
}));
let mockUser = { username: "m@example.com", role: "individual" };
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ user: mockUser }) }));

const POLICIES = [
  { document_id: "pol1", filename: "apex.pdf", owner: "m@example.com" },
  { document_id: "pol2", filename: "summit.pdf", owner: "m@example.com" },
];

beforeEach(() => {
  mockUser = { username: "m@example.com", role: "individual" };
  window.location.hash = "/chat";
  api.listPatients.mockResolvedValue([]);
  api.chatSuggestions.mockResolvedValue({ questions: ["What are my copays?"] });
  api.getPolicySummary.mockResolvedValue({
    deductible: { description: "Individual: $1,500" }, out_of_pocket_max: { description: "$6,000" },
    copayments: [{ service: "Specialist Office Visit", amount: "$50 copay" }],
  });
  Element.prototype.scrollIntoView = vi.fn();
  api.listPolicies.mockResolvedValue(POLICIES);
  api.health.mockResolvedValue({ mode: "demo" });
  let n = 0;
  api.chat.mockImplementation(async (q, policy, conv) => ({
    answer: `answer to ${q}`,
    citations: [],
    follow_up_suggestions: [],
    conversation_id: conv || `conv${++n}`,
  }));
});
afterEach(() => vi.clearAllMocks());

async function ask(text) {
  await userEvent.type(screen.getByPlaceholderText(/ask/i), `${text}{Enter}`);
  await screen.findByText(`answer to ${text}`);
}

test("follow-up questions send back the conversation id", async () => {
  render(<ChatAssistant />);
  await waitFor(() => expect(screen.getByLabelText("Policy")).toHaveValue("pol1"));
  await ask("Is an MRI covered?");
  await ask("Does it need approval?");
  expect(api.chat.mock.calls.map((c) => c.slice(1, 3))).toEqual([
    ["pol1", null],
    ["pol1", "conv1"],
  ]);
});

test("changing policy or New conversation starts over", async () => {
  render(<ChatAssistant />);
  await waitFor(() => expect(screen.getByLabelText("Policy")).toHaveValue("pol1"));
  await ask("Is an MRI covered?");
  await userEvent.selectOptions(screen.getByLabelText("Policy"), "pol2");
  expect(screen.queryByText("answer to Is an MRI covered?")).toBeNull();
  await ask("Is hospice covered?");
  await userEvent.click(screen.getByRole("button", { name: "New conversation" }));
  await ask("Is acupuncture covered?");
  expect(api.chat.mock.calls.map((c) => c.slice(1, 3))).toEqual([
    ["pol1", null],
    ["pol2", null],
    ["pol2", null],
  ]);
});


test("privacy notice says where questions go", async () => {
  api.health.mockResolvedValue({ mode: "live" });
  render(<ChatAssistant />);
  expect(await screen.findByRole("note")).toHaveTextContent("sent to Anthropic");
  expect(screen.getByRole("note")).toHaveTextContent("up to an hour");
});

test("demo mode notice says questions stay on the server", async () => {
  render(<ChatAssistant />);
  expect(await screen.findByRole("note")).toHaveTextContent("not sent to any outside service");
});


test("individuals can ask across all their documents", async () => {
  render(<ChatAssistant />);
  await waitFor(() => expect(screen.getByLabelText("Policy")).toHaveValue("pol1"));
  await userEvent.selectOptions(screen.getByLabelText("Policy"), "");
  await ask("What is my deductible?");
  expect(api.chat.mock.calls[0][1]).toBeUndefined();
});

test("hospital staff must pick a patient; questions carry the patient", async () => {
  mockUser = { username: "s@h.example", role: "hospital_staff", org_id: "org1" };
  api.listPolicies.mockResolvedValue([
    { document_id: "d1", filename: "p1.pdf", org_id: "org1", patient_id: "p1" },
    { document_id: "d2", filename: "p2.pdf", org_id: "org1", patient_id: "p2" },
  ]);
  api.listPatients.mockResolvedValue([
    { patient_id: "p1", name: "Pat One", reference: "MRN-1", documents: [{ document_id: "d1" }] },
    { patient_id: "p2", name: "Pat Two", reference: "", documents: [{ document_id: "d2" }] },
  ]);
  render(<ChatAssistant />);
  expect(await screen.findByText(/Choose a patient to ask/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Ask|Send/ })).toBeDisabled();
  await userEvent.selectOptions(screen.getByLabelText("Patient"), "p1");
  const policyOptions = [...screen.getByLabelText("Policy").options].map((o) => o.textContent);
  expect(policyOptions).toEqual(["All of this patient's documents", "Pat One — p1.pdf"]);
  await ask("Is an MRI covered?");
  expect(api.chat.mock.calls[0].slice(1)).toEqual([undefined, null, "p1"]);
});

test("hospital staff can search patients by name", async () => {
  mockUser = { username: "s@h.example", role: "hospital_staff", org_id: "org1" };
  api.listPolicies.mockResolvedValue([]);
  api.listPatients.mockResolvedValue([
    { patient_id: "p1", name: "Maria Lopez", reference: "MRN-1", documents: [] },
    { patient_id: "p2", name: "Mark Chen", reference: "", documents: [] },
    { patient_id: "p3", name: "Ann Lopez-Hart", reference: "", documents: [] },
  ]);
  render(<ChatAssistant />);
  const names = () => [...screen.getByLabelText("Patient").options].slice(1).map((o) => o.value);
  await waitFor(() => expect(names()).toEqual(["p1", "p2", "p3"]));
  // optional: nothing to type until the search is opened
  expect(screen.queryByLabelText("Search patients by name")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Search patients" }));
  const box = screen.getByLabelText("Search patients by name");
  await userEvent.type(box, "lopez");
  expect(names()).toEqual(["p1", "p3"]);
  expect(screen.getByText("2 matches")).toBeInTheDocument();
  await userEvent.type(box, " ann");
  expect(names()).toEqual(["p3"]);
  await userEvent.type(box, "{Enter}");
  expect(screen.getByLabelText("Patient")).toHaveValue("p3");
  // the chosen patient stays listed while the search changes
  await userEvent.clear(box);
  await userEvent.type(box, "zzz");
  expect(screen.getByText("No patients match")).toBeInTheDocument();
  expect(names()).toEqual(["p3"]);
  await userEvent.click(screen.getByRole("button", { name: "Close search" }));
  expect(names()).toEqual(["p1", "p2", "p3"]);
});

test("patient search also matches the email of a patient who shared", async () => {
  mockUser = { username: "s@h.example", role: "hospital_staff", org_id: "org1" };
  api.listPolicies.mockResolvedValue([]);
  api.listPatients.mockResolvedValue([
    { patient_id: "p1", name: "Maria Lopez", reference: "", documents: [] },
    { patient_id: "p2", name: "J. Doe", linked_username: "jubril@example.com", reference: "", documents: [] },
  ]);
  render(<ChatAssistant />);
  await userEvent.click(await screen.findByRole("button", { name: "Search patients" }));
  await userEvent.type(screen.getByLabelText("Search patients by name"), "Jubril");
  expect([...screen.getByLabelText("Patient").options].slice(1).map((o) => o.value)).toEqual(["p2"]);
});

test("individuals have no patient search", async () => {
  render(<ChatAssistant />);
  await screen.findByLabelText("Policy");
  expect(screen.queryByRole("button", { name: "Search patients" })).not.toBeInTheDocument();
});

test("a patient link preselects the patient", async () => {
  mockUser = { username: "s@h.example", role: "hospital_staff", org_id: "org1" };
  window.location.hash = "/chat?patient=p2";
  api.listPolicies.mockResolvedValue([]);
  api.listPatients.mockResolvedValue([{ patient_id: "p2", name: "Pat Two", reference: "", documents: [] }]);
  render(<ChatAssistant />);
  await waitFor(() => expect(screen.getByLabelText("Patient")).toHaveValue("p2"));
});


test("clicking a starter question asks it straight away", async () => {
  render(<ChatAssistant />);
  await userEvent.click(await screen.findByRole("button", { name: "What are my copays?" }));
  await waitFor(() => expect(api.chat).toHaveBeenCalledWith("What are my copays?", expect.anything(), null, undefined));
  expect(screen.getByPlaceholderText(/ask/i)).toHaveValue("");
  expect(api.chatSuggestions).toHaveBeenCalled();
});

test("plan at a glance shows the selected plan's key numbers", async () => {
  render(<ChatAssistant />);
  const glance = await screen.findByRole("complementary", { name: "Plan at a glance" });
  expect(glance).toHaveTextContent("Individual: $1,500");
  expect(glance).toHaveTextContent("Specialist Office Visit");
});

test("answers show suggested next steps with their source", async () => {
  api.chat.mockResolvedValueOnce({
    answer: "MRI needs prior authorization.", citations: [], follow_up_suggestions: [],
    conversation_id: "c1",
    next_steps: [{ text: "Ask your provider to request prior authorization.", document_id: "pol1",
                   page_number: 3, section: "PRIOR AUTHORIZATION" }],
  });
  render(<ChatAssistant />);
  await waitFor(() => expect(screen.getByLabelText("Policy")).toHaveValue("pol1"));
  await userEvent.type(screen.getByPlaceholderText(/ask/i), "Is MRI covered?{Enter}");
  expect(await screen.findByText("What to check")).toBeInTheDocument();
  expect(screen.getByText(/based on page 3, PRIOR AUTHORIZATION/)).toBeInTheDocument();
});

test("citations from scanned pages say to check the original", async () => {
  api.chat.mockResolvedValueOnce({
    answer: "Up to 20 visits.", follow_up_suggestions: [], conversation_id: "c1",
    citations: [
      { document_id: "pol1", page_number: 2, section: "BENEFITS", excerpt: "20 visits", confidence: "supported", from_scan: true },
      { document_id: "pol1", page_number: 1, section: "SUMMARY", excerpt: "PPO", confidence: "supported", from_scan: false },
    ],
  });
  render(<ChatAssistant />);
  await waitFor(() => expect(screen.getByLabelText("Policy")).toHaveValue("pol1"));
  await userEvent.type(screen.getByPlaceholderText(/ask/i), "How many visits?{Enter}");
  expect(await screen.findAllByText("From a scanned page — check the original")).toHaveLength(1);
});

test("answers are laid out: lead, plan differences, quotes per plan, keep in mind", async () => {
  api.chat.mockResolvedValueOnce({
    answer: "full plain text", follow_up_suggestions: [], conversation_id: "c1",
    lead: "Your question matches 2 of your plans, so each is shown separately.",
    policy_says: [
      { document_id: "a", document_name: "Gold PPO Plan", page_number: 1, section: "COSTS", quote: "Deductible: $1,500" },
      { document_id: "b", document_name: "Bronze HDHP 7000", page_number: 2, section: "SUMMARY", quote: "Deductible: $7,000", from_scan: true },
    ],
    differences: [{ topic: "Deductible", values: [
      { document_id: "a", document_name: "Gold PPO Plan", value: "$1,500 individual" },
      { document_id: "b", document_name: "Bronze HDHP 7000", value: "$7,000 individual" }] }],
    keep_in_mind: "This explains your policy document. It is not a coverage decision.",
    citations: [{ document_id: "a", page_number: 1, section: "COSTS", excerpt: "x", confidence: "supported" }],
  });
  render(<ChatAssistant />);
  await waitFor(() => expect(screen.getByLabelText("Policy")).toHaveValue("pol1"));
  await userEvent.type(screen.getByPlaceholderText(/ask/i), "What is my deductible?{Enter}");
  expect(await screen.findByText(/matches 2 of your plans/)).toBeInTheDocument();
  expect(screen.queryByText("full plain text")).toBeNull();
  const diff = screen.getByRole("note", { name: "Plans differ" });
  expect(diff).toHaveTextContent("Deductible: Gold PPO Plan: $1,500 · Bronze HDHP 7000: $7,000");
  expect(screen.getByRole("region", { name: "What Gold PPO Plan says" })).toHaveTextContent("Deductible: $1,500");
  expect(screen.getByRole("region", { name: "What Bronze HDHP 7000 says" })).toHaveTextContent("from a scanned page");
  expect(screen.getByRole("note", { name: "Keep in mind" })).toHaveTextContent("not a coverage decision");
  expect(screen.getByText("All sources (1)")).toBeInTheDocument();
});
