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
 * Strategy: WebSocket connections go DIRECTLY to the backend (not through the
 * Next.js proxy) because Next.js rewrites() do not reliably proxy WebSocket
 * protocol upgrades.
 *
 * In the browser:
 *   1. If NEXT_PUBLIC_WS_URL is set, use it as-is (full explicit override).
 *   2. Otherwise, build the URL dynamically:
 *      - hostname  = window.location.hostname  (adapts to any host/IP/domain)
 *      - port      = extracted from NEXT_PUBLIC_API_URL (the backend port)
 *      - protocol  = ws: or wss: to match the page's http/https scheme
 *
 * Example (backend on :9000, frontend on :3001, accessed via any hostname):
 *   NEXT_PUBLIC_API_URL=http://localhost:9000
 *   → ws://<current-hostname>:9000/ws/task_id
 *
 * On the server side, uses the configured WS URL directly.
 */
export function getWsUrl(endpoint: string): string {
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  if (typeof window !== 'undefined') {
    // 1. Explicit full override
    if (process.env.NEXT_PUBLIC_WS_URL) {
      const base = process.env.NEXT_PUBLIC_WS_URL.replace(/\/$/, '');
      return `${base}${path}`;
    }
    // 2. Dynamic: same hostname the user is on + backend port from API config
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9000';
      const parsed = new URL(apiBase);
      // Extract just the port from the configured API URL (e.g. 9000)
      const backendPort = parsed.port || (parsed.protocol === 'https:' ? '443' : '80');
      // Use window.location.hostname so it works regardless of the IP/domain
      // the user accesses the frontend from
      return `${protocol}//${window.location.hostname}:${backendPort}${path}`;
    } catch {
      // Fallback: same origin (works when a reverse proxy is in front)
      return `${protocol}//${window.location.host}${path}`;
    }
  }
  // Server-side: use the explicit WS URL from config
  const base = config.wsUrl.replace(/\/$/, '');
  return `${base}${path}`;
}
