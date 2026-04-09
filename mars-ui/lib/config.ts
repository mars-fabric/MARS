/**
 * Configuration for MARS UI
 * Uses environment variables with fallbacks for local development
 */

// Derive the API base URL once (used for both REST and WebSocket fallback)
const _apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
 * Get the full WebSocket URL for a given endpoint
 */
export function getWsUrl(endpoint: string): string {
  const base = config.wsUrl.replace(/\/$/, '');
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return `${base}${path}`;
}
