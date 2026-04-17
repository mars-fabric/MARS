/** @type {import('next').NextConfig} */
const path = require('path');
const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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

  experimental: {
    proxyTimeout: 300_000,
  },

  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: '/ws/:path*',
        destination: `${backendUrl}/ws/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
