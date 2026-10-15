import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
import { forgetTabToken } from "../api/token";

// Node-environment tests (catalogues, tokens, schema) share this file but have no DOM.
const hasDom = typeof window !== "undefined";

afterEach(() => {
  forgetTabToken();
  if (!hasDom) return;
  cleanup();
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.lang = "en";
});

if (hasDom) installDomStubs();

function installDomStubs(): void {
// jsdom lacks these; Radix and TanStack Virtual call them.
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;
Element.prototype.scrollIntoView ??= function scrollIntoView() {};
Element.prototype.hasPointerCapture ??= () => false;
Element.prototype.releasePointerCapture ??= () => {};
Element.prototype.setPointerCapture ??= () => {};
window.matchMedia ??= (query: string) =>
  ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }) as MediaQueryList;

// jsdom lays nothing out, so every element measures 0 px and a virtualised table would
// render no rows. Give the table's scroll container a desktop-sized box.
for (const [property, size] of [["offsetHeight", 800], ["offsetWidth", 1024]] as const) {
  const native = Object.getOwnPropertyDescriptor(HTMLElement.prototype, property);
  Object.defineProperty(HTMLElement.prototype, property, {
    configurable: true,
    get(this: HTMLElement) {
      return this.dataset.testid === "table-scroll" ? size : (native?.get?.call(this) ?? 0);
    },
  });
}
}
