import { useSyncExternalStore } from "react";

function getHash() {
  return window.location.hash.replace(/^#/, "") || "/";
}

const listeners = new Set();
function subscribe(cb) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

window.addEventListener("hashchange", () => {
  listeners.forEach((cb) => cb());
});

export function useHashPath() {
  return useSyncExternalStore(subscribe, getHash);
}

export function navigate(path) {
  window.location.hash = path;
}
