import { afterEach, describe, expect, it } from "vitest";
import { buildApiUrl, buildWsUrl } from "../../utils/urlBuilder";

const wsOrigin =
  window.location.protocol === "https:"
    ? `wss://${window.location.host}`
    : `ws://${window.location.host}`;

describe("urlBuilder", () => {
  afterEach(() => {
    window.ENV = undefined;
  });

  describe("buildApiUrl", () => {
    it("avoids duplicate /api prefix when API_URL is /api", () => {
      window.ENV = { API_URL: "/api" };
      expect(buildApiUrl("/api/targets")).toBe("/api/targets");
    });

    it("handles API_URL with trailing slash", () => {
      window.ENV = { API_URL: "/api/" };
      expect(buildApiUrl("/api/presets")).toBe("/api/presets");
    });

    it("handles empty API_URL", () => {
      window.ENV = { API_URL: "" };
      expect(buildApiUrl("/api/targets")).toBe("/api/targets");
    });

    it("handles root API_URL", () => {
      window.ENV = { API_URL: "/" };
      expect(buildApiUrl("/api/health")).toBe("/api/health");
    });

    it("merges non-prefixed paths with /api base", () => {
      window.ENV = { API_URL: "/api" };
      expect(buildApiUrl("/targets")).toBe("/api/targets");
    });

    it("handles absolute API_URL values", () => {
      window.ENV = { API_URL: "https://example.com/api" };
      expect(buildApiUrl("/api/targets")).toBe(
        "https://example.com/api/targets",
      );
    });
  });

  describe("buildWsUrl", () => {
    it("builds absolute WS URL from relative /api/ws", () => {
      window.ENV = { WS_URL: "/api/ws" };
      expect(buildWsUrl("/api/ws")).toBe(`${wsOrigin}/api/ws`);
    });

    it("converts https WS base to wss", () => {
      window.ENV = { WS_URL: "https://dashboard.example.com/api/ws" };
      expect(buildWsUrl("/api/ws")).toBe("wss://dashboard.example.com/api/ws");
    });

    it("merges WS base and endpoint path without duplicates", () => {
      window.ENV = { WS_URL: "ws://dashboard.example.com/api" };
      expect(buildWsUrl("/api/ws")).toBe("ws://dashboard.example.com/api/ws");
    });

    it("falls back to current host when WS_URL is empty", () => {
      window.ENV = { WS_URL: "" };
      expect(buildWsUrl("/api/ws")).toBe(`${wsOrigin}/api/ws`);
    });
  });
});

