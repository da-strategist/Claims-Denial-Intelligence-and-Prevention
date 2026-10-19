import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatAssistant from "./ChatAssistant";
import { api } from "../services/api";

vi.mock("../services/api", () => ({
  api: { listPolicies: vi.fn(), chat: vi.fn() },
}));

const POLICIES = [
  { document_id: "pol1", filename: "apex.pdf" },
  { document_id: "pol2", filename: "summit.pdf" },
];

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
  api.listPolicies.mockResolvedValue(POLICIES);
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
  await waitFor(() => expect(screen.getByRole("combobox")).toHaveValue("pol1"));
  await ask("Is an MRI covered?");
  await ask("Does it need approval?");
  expect(api.chat.mock.calls.map((c) => c.slice(1))).toEqual([
    ["pol1", null],
    ["pol1", "conv1"],
  ]);
});

test("changing policy or New conversation starts over", async () => {
  render(<ChatAssistant />);
  await waitFor(() => expect(screen.getByRole("combobox")).toHaveValue("pol1"));
  await ask("Is an MRI covered?");
  await userEvent.selectOptions(screen.getByRole("combobox"), "pol2");
  expect(screen.queryByText("answer to Is an MRI covered?")).toBeNull();
  await ask("Is hospice covered?");
  await userEvent.click(screen.getByRole("button", { name: "New conversation" }));
  await ask("Is acupuncture covered?");
  expect(api.chat.mock.calls.map((c) => c.slice(1))).toEqual([
    ["pol1", null],
    ["pol2", null],
    ["pol2", null],
  ]);
});
