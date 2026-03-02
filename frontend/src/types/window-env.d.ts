export {};

declare global {
  interface Window {
    ENV?: {
      API_URL?: string;
      WS_URL?: string;
    };
  }
}

