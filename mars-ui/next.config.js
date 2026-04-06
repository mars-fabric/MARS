/** @type {import('next').NextConfig} */
const path = require('path');
const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const nextConfig = {
  // Disable strict mode to prevent double-render in dev (a common lag source)
  reactStrictMode: false,

  // Disable the "X-Powered-By" header
  poweredByHeader: false,

  // Explicitly set turbopack root to avoid conflicts with multiple lockfiles
  turbopack: {
    root: path.resolve(__dirname),
  },

  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
