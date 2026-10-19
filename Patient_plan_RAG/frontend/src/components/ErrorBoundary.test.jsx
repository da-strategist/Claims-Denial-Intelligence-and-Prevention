import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ErrorBoundary from "./ErrorBoundary";

let shouldThrow;
function Flaky() {
  if (shouldThrow) throw new Error("boom");
  return <p>page content</p>;
}

beforeEach(() => {
  shouldThrow = true;
  vi.spyOn(console, "error").mockImplementation(() => {});
});
afterEach(() => vi.restoreAllMocks());

test("renders children when nothing throws", () => {
  shouldThrow = false;
  render(<ErrorBoundary><Flaky /></ErrorBoundary>);
  expect(screen.getByText("page content")).toBeInTheDocument();
});

test("shows fallback with the error message instead of blanking", () => {
  render(<ErrorBoundary><Flaky /></ErrorBoundary>);
  expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong on this page");
  expect(screen.getByRole("alert")).toHaveTextContent("boom");
});

test("Try again re-renders the children", async () => {
  render(<ErrorBoundary><Flaky /></ErrorBoundary>);
  shouldThrow = false;
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(screen.getByText("page content")).toBeInTheDocument();
});

test("Go to Dashboard calls onHome; hidden without it", async () => {
  const onHome = vi.fn();
  const { unmount } = render(<ErrorBoundary onHome={onHome}><Flaky /></ErrorBoundary>);
  await userEvent.click(screen.getByRole("button", { name: "Go to Dashboard" }));
  expect(onHome).toHaveBeenCalledOnce();
  unmount();
  render(<ErrorBoundary><Flaky /></ErrorBoundary>);
  expect(screen.queryByRole("button", { name: "Go to Dashboard" })).toBeNull();
});

test("custom fallback receives the error", () => {
  render(
    <ErrorBoundary fallback={({ error }) => <p>custom: {error.message}</p>}>
      <Flaky />
    </ErrorBoundary>
  );
  expect(screen.getByText("custom: boom")).toBeInTheDocument();
});
