/**
 * Configuration for MARS UI
 * Uses environment variables with fallbacks for local development
 */

// Derive the API base URL once (used for both REST and WebSocket fallback)
const _apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

export const config = {
  // API URL for REST endpoints
  apiUrl: _apiBase,

  // WebSocket URL — if NEXT_PUBLIC_WS_URL is not set, derive from apiUrl
  // so both ports always share the same host:port (no separate env var needed).
  // e.g. http://EC2-IP:8001 → ws://EC2-IP:8001
  wsUrl: process.env.NEXT_PUBLIC_WS_URL || _apiBase.replace(/^https?/, m => m === 'https' ? 'wss' : 'ws'),

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
 * In the browser we can't use `localhost` because that resolves to the user's
 * own machine, not the EC2 server. Instead we:
 *   1. Use NEXT_PUBLIC_WS_URL directly if it is explicitly set.
 *   2. Parse NEXT_PUBLIC_API_URL for the backend port, then substitute
 *      window.location.hostname (the real server IP/domain) so the WS
 *      connection lands on the same host the browser is already talking to.
 *   3. Fall back to window.location.host (same-origin) if nothing is set.
 */
export function getWsUrl(endpoint: string): string {
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;

  if (typeof window !== 'undefined') {
    // Explicit WS override — trust it completely
    if (process.env.NEXT_PUBLIC_WS_URL) {
      return `${process.env.NEXT_PUBLIC_WS_URL.replace(/\/$/, '')}${path}`;
    }

    // Derive from NEXT_PUBLIC_API_URL: keep the port, use the real browser hostname
    const apiBase = process.env.NEXT_PUBLIC_API_URL || '';
    try {
      const url = new URL(apiBase || 'http://localhost:8001');
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      // If API URL uses localhost/127.0.0.1 (a server-side convenience value),
      // replace it with the hostname the browser used to reach the page.
      const isLocal = url.hostname === 'localhost' || url.hostname === '127.0.0.1';
      const host = isLocal ? window.location.hostname : url.hostname;
      const port = url.port;
      return `${protocol}//${host}${port ? ':' + port : ''}${path}`;
    } catch {
      // Absolute fallback: same origin as the page
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${protocol}//${window.location.host}${path}`;
    }
  }

  // Server-side (SSR): use the configured WS URL directly
  const base = config.wsUrl.replace(/\/$/, '');
  return `${base}${path}`;
}
