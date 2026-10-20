import { errorMessage } from "./api";

const res = (status, body, headers = {}) =>
  new Response(typeof body === "string" ? body : JSON.stringify(body), { status, headers });

test("uses FastAPI string detail", async () => {
  expect(await errorMessage(res(413, { detail: "File exceeds the 20 MB limit" })))
    .toBe("413: File exceeds the 20 MB limit");
});

test("summarises validation errors", async () => {
  const body = { detail: [{ loc: ["body", "question"], msg: "String should have at most 2000 characters" }] };
  expect(await errorMessage(res(422, body)))
    .toBe("422: question: String should have at most 2000 characters");
});

test("adds Retry-After for rate limits", async () => {
  const r = res(429, { detail: "Too many requests, please slow down." }, { "Retry-After": "12" });
  expect(await errorMessage(r)).toBe("429: Too many requests, please slow down. (try again in 12s)");
});

test("falls back to raw text for non-JSON bodies", async () => {
  expect(await errorMessage(res(502, "Bad gateway"))).toBe("502: Bad gateway");
});

test("any 401 fires the auth-required event", async () => {
  const { api, AUTH_REQUIRED_EVENT } = await import("./api");
  const heard = vi.fn();
  window.addEventListener(AUTH_REQUIRED_EVENT, heard);
  globalThis.fetch = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ detail: "Sign in required" }), { status: 401 }));
  await expect(api.listPolicies()).rejects.toThrow("401: Sign in required");
  expect(heard).toHaveBeenCalledOnce();
  window.removeEventListener(AUTH_REQUIRED_EVENT, heard);
});
