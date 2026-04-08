#!/usr/bin/env node
/**
 * Custom Next.js server with WebSocket proxy.
 *
 * Why this exists:
 *   Next.js rewrites() cannot proxy WebSocket upgrade requests.  In production
 *   the backend may only be reachable on a private port (e.g. 9000) while the
 *   frontend is exposed on a different port (e.g. 3001).  When users access the
 *   app via an SSH tunnel or a load-balancer they only have the *frontend* port
 *   available, so direct browser → backend WebSocket connections fail.
 *
 *   This server listens on the frontend port and transparently upgrades
 *   /ws/* requests to the backend, so the browser only ever needs the one port.
 *
 * Usage:
 *   Development:  NODE_ENV=development node server.js
 *   Production:   NODE_ENV=production  node server.js
 *
 *   Environment variables (all optional):
 *     PORT                   – port to listen on (default: 3001 in prod, 3002 in dev)
 *     HOST                   – bind address (default: 0.0.0.0)
 *     NEXT_PUBLIC_API_URL    – backend base URL, e.g. http://localhost:9000
 */

'use strict';

const { createServer } = require('http');
const { parse }        = require('url');
const next             = require('next');
const httpProxy        = require('http-proxy');

const dev      = process.env.NODE_ENV !== 'production';
const hostname = process.env.HOST || '0.0.0.0';
const port     = parseInt(process.env.PORT || (dev ? '3002' : '3001'), 10);

// Where REST + WebSocket connections are forwarded on the server side.
// This is only needed for outgoing proxy calls; the browser never sees it.
const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9000';

const app    = next({ dev, hostname: 'localhost', port });
const handle = app.getRequestHandler();

// ── WebSocket proxy ────────────────────────────────────────────────────────
const proxy = httpProxy.createProxyServer({
  target:       backendUrl,
  ws:           true,
  changeOrigin: true,
});

proxy.on('error', (err, req, res) => {
  console.error('[WS Proxy] Error:', err.message);
  // res may be a socket (upgrade path) – only write HTTP headers when possible
  if (res && typeof res.writeHead === 'function' && !res.headersSent) {
    res.writeHead(502, { 'Content-Type': 'text/plain' });
    res.end('WebSocket proxy error: ' + err.message);
  }
});

// ── Boot ───────────────────────────────────────────────────────────────────
app.prepare().then(() => {
  const server = createServer(async (req, res) => {
    try {
      const parsedUrl = parse(req.url, true);
      await handle(req, res, parsedUrl);
    } catch (err) {
      console.error('[Server] Unhandled error for', req.url, err);
      res.statusCode = 500;
      res.end('Internal server error');
    }
  });

  // Forward all /ws/* WebSocket upgrades to the backend
  server.on('upgrade', (req, socket, head) => {
    const { pathname } = parse(req.url);
    if (pathname && pathname.startsWith('/ws')) {
      console.log(`[WS Proxy] ${pathname}  →  ${backendUrl}${pathname}`);
      proxy.ws(req, socket, head);
    } else {
      socket.destroy();
    }
  });

  server.listen(port, hostname, () => {
    const localUrl = `http://localhost:${port}`;
    console.log(`> Ready on ${localUrl}  (${dev ? 'development' : 'production'})`);
    console.log(`> WebSocket proxy: ws://localhost:${port}/ws/*  →  ${backendUrl}/ws/*`);

    // In dev mode open the browser automatically (mirrors old dev-with-browser.js)
    if (dev) {
      import('open').then(({ default: open }) => {
        open(localUrl).catch(() => {});
      }).catch(() => {});
    }
  });
});
