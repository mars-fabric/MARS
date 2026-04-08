/** @type {import('next').NextConfig} */
const path = require('path');
// Backend REST API base URL. Used only for server-side proxy rewrites.
// WebSocket connections bypass this proxy and connect directly to the backend.
const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9000';

const nextConfig = {
  // Disable strict mode to prevent double-render in dev (a common lag source)
  reactStrictMode: false,

  // Disable the "X-Powered-By" header
  poweredByHeader: false,

  // Allow external hosts in development
  allowedDevOrigins: ['100.88.49.58'],

  // Explicitly set turbopack root to avoid conflicts with multiple lockfiles
  turbopack: {
    root: path.resolve(__dirname),
  },

  async rewrites() {
    return [
      // REST API calls are proxied through Next.js (same-origin, no CORS needed).
      // WebSocket connections are NOT proxied here — Next.js rewrites don't
      // reliably handle WebSocket protocol upgrades. Instead, getWsUrl() in
      // lib/config.ts builds the WS URL directly to the backend port.
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
