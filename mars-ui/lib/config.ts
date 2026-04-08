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
 * Uses same-origin so the browser connects to the frontend port.
 * server.js proxies the /ws/* upgrade to the backend internally.
 */
export function getWsUrl(endpoint: string): string {
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}${path}`;
  }
  // Server-side fallback
  const base = config.wsUrl.replace(/\/$/, '');
  return `${base}${path}`;
}
