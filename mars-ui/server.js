'use strict';

/**
 * Custom Next.js server with WebSocket proxy.
 *
 * Solves: Next.js `next start` does not proxy WebSocket upgrade requests,
 * so ws://host:FRONTEND_PORT/ws/* would fail. This server intercepts the
 * Upgrade header at the Node.js HTTP level and forwards it to the backend.
 *
 * Browser  →  ws://host:PORT/ws/task_id       (same port as the page)
 * server.js →  ws://localhost:BACKEND/ws/task_id  (internal)
 *
 * Environment variables:
 *   PORT                 - port this server listens on (default: 3000)
 *   NEXT_PUBLIC_API_URL  - backend base URL           (default: http://localhost:8000)
 */

const { createServer } = require('http');
const { parse } = require('url');
const next = require('next');
const httpProxy = require('http-proxy');

const dev = process.env.NODE_ENV !== 'production';
const port = parseInt(process.env.PORT || '3000', 10);
const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const app = next({ dev });
const handle = app.getRequestHandler();

const proxy = httpProxy.createProxyServer({
  target: backendUrl,
  ws: true,
  changeOrigin: true,
});

proxy.on('error', (err, req, socket) => {
  console.error('[WS Proxy] error:', err.message, 'url:', req?.url);
  if (socket && typeof socket.destroy === 'function') socket.destroy();
});

app.prepare().then(() => {
  const server = createServer((req, res) => {
    handle(req, res, parse(req.url, true));
  });

  // Forward WebSocket upgrades for /ws/* to the backend
  server.on('upgrade', (req, socket, head) => {
    if (req.url && req.url.startsWith('/ws/')) {
      console.log(`[WS Proxy] ${req.url}  →  ${backendUrl}${req.url}`);
      proxy.ws(req, socket, head);
    } else {
      socket.write('HTTP/1.1 404 Not Found\r\n\r\n');
      socket.destroy();
    }
  });

  server.listen(port, (err) => {
    if (err) throw err;
    console.log(`> Ready on http://localhost:${port}`);
    console.log(`> WebSocket /ws/* proxied to ${backendUrl}`);
  });
});
