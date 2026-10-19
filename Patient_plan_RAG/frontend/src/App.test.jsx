import { act, render, screen } from "@testing-library/react";
import App from "./App";

// Stub pages so no API calls run; Dashboard crashes on render.
vi.mock("./pages/Dashboard", () => ({
  default: () => {
    throw new Error("dashboard exploded");
  },
}));
vi.mock("./pages/ChatAssistant", () => ({ default: () => <p>chat page</p> }));
vi.mock("./pages/PolicyViewer", () => ({ default: () => <p>policies page</p> }));
vi.mock("./pages/CoverageAssessment", () => ({ default: () => <p>coverage page</p> }));
vi.mock("./pages/PriorAuth", () => ({ default: () => <p>auth page</p> }));

function goTo(path) {
  act(() => {
    window.location.hash = path;
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
}

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  window.location.hash = "/";
});
afterEach(() => vi.restoreAllMocks());

test("a crashing page keeps the disclaimer and navigation on screen", () => {
  render(<App />);
  expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong on this page");
  expect(screen.getByText(/Demonstration Only/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Ask a Question/ })).toBeInTheDocument();
});

test("navigating away from a crashed page recovers", () => {
  render(<App />);
  goTo("/chat");
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.getByText("chat page")).toBeInTheDocument();
});

test("other pages render normally", () => {
  window.location.hash = "/coverage";
  render(<App />);
  expect(screen.getByText("coverage page")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).toBeNull();
});
