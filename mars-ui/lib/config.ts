/**
 * Configuration for MARS UI
 * Uses environment variables with fallbacks for local development
 */

export const config = {
  // API URL for REST endpoints
  apiUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',

  // WebSocket URL for real-time communication
  wsUrl: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',

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
 * In the browser:
 *   - If NEXT_PUBLIC_WS_URL is explicitly set, that value is used directly
 *     (allows pointing straight at the backend for advanced setups).
 *   - Otherwise the URL is derived from window.location so the connection
 *     always uses the same host/protocol as the page. Next.js rewrites the
 *     /ws/:path* path to the backend, identical to how getApiUrl works for
 *     HTTP requests (no hardcoded host/port, works on any environment).
 * On the server side, uses the configured WS URL directly.
 */
export function getWsUrl(endpoint: string): string {
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  if (typeof window !== 'undefined') {
    // Explicit override via env variable (e.g. wss://api.example.com)
    if (process.env.NEXT_PUBLIC_WS_URL) {
      const base = process.env.NEXT_PUBLIC_WS_URL.replace(/\/$/, '');
      return `${base}${path}`;
    }
    // Default: same-origin path proxied through Next.js (/ws/:path* rewrite)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}${path}`;
  }
  // Server-side: use the explicit WS URL from config
  const base = config.wsUrl.replace(/\/$/, '');
  return `${base}${path}`;
}
