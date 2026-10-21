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
  expect(await screen.findByText("Suggested next steps")).toBeInTheDocument();
  expect(screen.getByText(/based on page 3, PRIOR AUTHORIZATION/)).toBeInTheDocument();
});
