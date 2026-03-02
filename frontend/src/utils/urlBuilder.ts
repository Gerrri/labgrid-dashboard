const DEFAULT_API_PATH = "/api";
const DEFAULT_WS_PATH = "/api/ws";

function getConfiguredApiBase(): string {
  return window.ENV?.API_URL ?? import.meta.env.VITE_API_URL ?? "";
}

function getConfiguredWsBase(): string {
  return window.ENV?.WS_URL ?? import.meta.env.VITE_WS_URL ?? "";
}

function isAbsoluteUrl(value: string): boolean {
  return /^[a-z][a-z0-9+.-]*:\/\//i.test(value);
}

function normalizePath(path: string): string {
  const segments = path.split("/").filter(Boolean);
  return segments.length > 0 ? `/${segments.join("/")}` : "/";
}

function overlapCount(baseSegments: string[], pathSegments: string[]): number {
  const max = Math.min(baseSegments.length, pathSegments.length);
  for (let count = max; count > 0; count -= 1) {
    const baseSuffix = baseSegments.slice(-count).join("/");
    const pathPrefix = pathSegments.slice(0, count).join("/");
    if (baseSuffix === pathPrefix) {
      return count;
    }
  }
  return 0;
}

function mergePaths(basePath: string, path: string): string {
  const normalizedBase = normalizePath(basePath);
  const normalizedPath = normalizePath(path);

  if (normalizedBase === "/") {
    return normalizedPath;
  }
  if (normalizedPath === "/") {
    return normalizedBase;
  }

  const baseSegments = normalizedBase.split("/").filter(Boolean);
  const pathSegments = normalizedPath.split("/").filter(Boolean);
  const overlap = overlapCount(baseSegments, pathSegments);
  const merged = [...baseSegments, ...pathSegments.slice(overlap)];

  return `/${merged.join("/")}`;
}

function normalizeBase(rawBase: string): string {
  const trimmed = rawBase.trim();
  if (!trimmed || trimmed === "/") {
    return "";
  }
  return trimmed;
}

function normalizeWsProtocol(protocol: string): string {
  if (protocol === "https:") {
    return "wss:";
  }
  if (protocol === "http:") {
    return "ws:";
  }
  return protocol;
}

export function buildApiUrl(path: string): string {
  const configuredBase = normalizeBase(getConfiguredApiBase());
  const targetPath = path || DEFAULT_API_PATH;

  if (isAbsoluteUrl(configuredBase)) {
    const baseUrl = new URL(configuredBase);
    const mergedPath = mergePaths(baseUrl.pathname, targetPath);
    return `${baseUrl.origin}${mergedPath}`;
  }

  return mergePaths(configuredBase || "/", targetPath);
}

export function buildWsUrl(path: string = DEFAULT_WS_PATH): string {
  const configuredBase = normalizeBase(getConfiguredWsBase());
  const targetPath = path || DEFAULT_WS_PATH;

  if (!configuredBase) {
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const mergedPath = mergePaths("/", targetPath);
    return `${wsProtocol}//${window.location.host}${mergedPath}`;
  }

  if (isAbsoluteUrl(configuredBase)) {
    const baseUrl = new URL(configuredBase);
    const mergedPath = mergePaths(baseUrl.pathname, targetPath);
    const wsProtocol = normalizeWsProtocol(baseUrl.protocol);
    return `${wsProtocol}//${baseUrl.host}${mergedPath}`;
  }

  const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const mergedPath = mergePaths(configuredBase, targetPath);
  return `${wsProtocol}//${window.location.host}${mergedPath}`;
}
