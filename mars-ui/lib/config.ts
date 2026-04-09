/**
 * Configuration for MARS UI
 * Uses environment variables with fallbacks for local development
 */

// Derive the API base URL once (used for both REST and WebSocket fallback)
const _apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
 * WebSocket connections are proxied through Next.js rewrites (same origin),
 * so the browser connects to the Next.js server, which forwards to the backend.
 * This avoids cross-port/firewall issues.
 *
 * In the browser: use same-origin WebSocket (ws/wss based on page protocol,
 * same hostname and port as the page).
 * On the server side: use the configured WS URL directly.
 */
export function getWsUrl(endpoint: string): string {
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;

  if (typeof window !== 'undefined') {
    // Route through Next.js proxy (same origin) — the /ws/* rewrite in
    // next.config.js forwards to the backend, avoiding direct cross-port access.
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}${path}`;
  }

  // Server-side (SSR): use the configured WS URL directly
  const base = config.wsUrl.replace(/\/$/, '');
  return `${base}${path}`;
}
