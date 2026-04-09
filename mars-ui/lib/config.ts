/**
 * Configuration for MARS UI
 * Uses environment variables with fallbacks for local development
 */

// Derive the API base URL once (used for both REST and WebSocket fallback)
const _apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

export const config = {
  // API URL for REST endpoints
  apiUrl: _apiBase,

  // WebSocket URL — derived from apiUrl (http→ws, https→wss)
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
 * Both NEXT_PUBLIC_API_URL and NEXT_PUBLIC_WS_URL are set to "localhost:8001"
 * on the server (so the backend can talk to itself). But when this code runs
 * in the user's browser, "localhost" means the user's own machine — not EC2.
 *
 * Strategy:
 *   1. Determine the backend port from NEXT_PUBLIC_WS_URL or NEXT_PUBLIC_API_URL.
 *   2. Always use window.location.hostname (the real EC2 IP/domain the browser
 *      is already talking to) when the configured host is localhost/127.0.0.1.
 *   3. On the server side, use the config value as-is.
 */
export function getWsUrl(endpoint: string): string {
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;

  if (typeof window !== 'undefined') {
    // Pick the best available base URL (WS env var preferred, then API env var)
    const rawBase =
      process.env.NEXT_PUBLIC_WS_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      'ws://localhost:8001';

    try {
      // Normalise to a URL object (replace ws/wss with http/https for URL parser)
      const normalised = rawBase.replace(/^wss?:\/\//, 'http://');
      const parsed = new URL(normalised);
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';

      // Replace localhost/127.0.0.1 with the real server hostname
      const isLocal = parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1';
      const hostname = isLocal ? window.location.hostname : parsed.hostname;
      const port = parsed.port; // e.g. "8001"

      return `${protocol}//${hostname}${port ? ':' + port : ''}${path}`;
    } catch {
      // Fallback: same origin as the page
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${protocol}//${window.location.host}${path}`;
    }
  }

  // Server-side (SSR): use the configured WS URL directly
  const base = config.wsUrl.replace(/\/$/, '');
  return `${base}${path}`;
}
