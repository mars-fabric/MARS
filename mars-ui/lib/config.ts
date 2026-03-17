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
 * Get the full API URL for a given endpoint
 */
export function getApiUrl(endpoint: string): string {
  const base = config.apiUrl.replace(/\/$/, '');
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
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
