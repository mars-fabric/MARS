/**
 * Configuration for MARS UI
 * Uses environment variables with fallbacks for local development
 */

export const config = {
  // API URL for REST endpoints (also used to derive the WebSocket backend port)
  apiUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9000',

  // WebSocket URL — used only server-side or when NEXT_PUBLIC_WS_URL is set explicitly
  wsUrl: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:9000',

  // Work directory for task outputs and logs
  workDir: process.env.NEXT_PUBLIC_CMBAGENT_WORK_DIR || '~/Desktop/cmbdir',

  // Debug mode
  debug: process.env.NEXT_PUBLIC_DEBUG === 'true',
};

/**
 * Get the full API URL for a given endpoint.
 * In the browser, returns a relative path so requests go through the Next.js
 * proxy (same-origin, no CORS required). On the server side, returns the full URL.
 */
export function getApiUrl(endpoint: string): string {
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  // Browser: use relative path → routed through Next.js rewrite proxy
  if (typeof window !== 'undefined') {
    return path;
  }
  // Server-side (SSR/API routes): use full URL
  const base = config.apiUrl.replace(/\/$/, '');
  return `${base}${path}`;
}

/**
 * Get the full WebSocket URL for a given endpoint.
 *
 * Strategy: WebSocket connections are routed through the custom Next.js server
 * (server.js) which proxies /ws/* upgrade requests to the backend.  This means
 * the browser only needs to reach the *frontend* port — no extra backend port
 * needs to be exposed or tunnelled.
 *
 * In the browser:
 *   1. If NEXT_PUBLIC_WS_URL is set, use it as-is (full explicit override).
 *   2. Otherwise, use the same origin (host + port) the page was loaded from,
 *      which routes through the WS proxy on the frontend server.
 *
 * Example (frontend on :3001, backend on :9000, accessed via any hostname):
 *   → ws://<current-host>:3001/ws/task_id   (proxied to backend:9000)
 *
 * On the server side, uses the configured WS URL directly.
 */
export function getWsUrl(endpoint: string): string {
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  if (typeof window !== 'undefined') {
    // 1. Explicit full override (e.g. when backend is on a different domain)
    if (process.env.NEXT_PUBLIC_WS_URL) {
      const base = process.env.NEXT_PUBLIC_WS_URL.replace(/\/$/, '');
      return `${base}${path}`;
    }
    // 2. Same-origin: goes through the WS proxy on the frontend server.
    //    Works regardless of hostname, port forwarding, or load-balancer setup.
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}${path}`;
  }
  // Server-side: use the explicit WS URL from config
  const base = config.wsUrl.replace(/\/$/, '');
  return `${base}${path}`;
}
