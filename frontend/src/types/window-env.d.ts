export {};

declare global {
  interface Window {
    ENV?: {
      API_URL?: string;
      WS_URL?: string;
      API_TIMEOUT_MS?: string;
    };
  }
}
