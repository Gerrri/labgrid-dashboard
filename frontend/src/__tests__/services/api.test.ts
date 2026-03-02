import { describe, expect, it } from "vitest";
import { resolveApiTimeoutMs } from "../../services/api";

describe("resolveApiTimeoutMs", () => {
  it("returns the default timeout when the value is missing", () => {
    expect(resolveApiTimeoutMs(undefined)).toBe(10000);
  });

  it("returns the configured timeout for a valid positive integer", () => {
    expect(resolveApiTimeoutMs("30000")).toBe(30000);
  });

  it("falls back to the default timeout for invalid values", () => {
    expect(resolveApiTimeoutMs("abc")).toBe(10000);
    expect(resolveApiTimeoutMs("0")).toBe(10000);
    expect(resolveApiTimeoutMs("-1")).toBe(10000);
  });
});
