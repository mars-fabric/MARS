'use strict';

/**
 * Custom Next.js server with WebSocket proxy.
 * Uses ONLY Node.js built-in modules (http, net, url) — no external dependencies.
 *
 * Browser  →  ws://host:PORT/ws/task_id          (same port as the page)
 * server.js →  ws://localhost:BACKEND/ws/task_id  (internal TCP tunnel)
 *
 * Environment variables:
 *   PORT                 - port this server listens on (default: 3000)
 *   NEXT_PUBLIC_API_URL  - backend base URL           (default: http://localhost:8000)
 */

const { createServer } = require('http');
const { parse } = require('url');
const net = require('net');
const next = require('next');

const dev = process.env.NODE_ENV !== 'production';
const port = parseInt(process.env.PORT || '3000', 10);
const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Parse backend host + port from the configured URL
const parsedBackend = new URL(backendUrl);
const backendHost = parsedBackend.hostname;
const backendPort = parseInt(
  parsedBackend.port || (parsedBackend.protocol === 'https:' ? '443' : '80'),
  10
);

const app = next({ dev });
const handle = app.getRequestHandler();

app.prepare().then(() => {
  const server = createServer((req, res) => {
    handle(req, res, parse(req.url, true));
  });

  // Proxy WebSocket upgrades for /ws/* to the backend using a raw TCP tunnel.
  // This works without http-proxy — just two sockets piped together.
  server.on('upgrade', (req, socket, head) => {
    if (!req.url || !req.url.startsWith('/ws/')) {
      socket.write('HTTP/1.1 404 Not Found\r\n\r\n');
      socket.destroy();
      return;
    }

    console.log(`[WS Proxy] ${req.url}  →  ${backendHost}:${backendPort}`);

    const backendSocket = net.connect(backendPort, backendHost, () => {
      // Reconstruct the HTTP upgrade request to forward to the backend
      const headers = Object.entries(req.headers)
        .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
        .join('\r\n');

      backendSocket.write(
        `${req.method} ${req.url} HTTP/${req.httpVersion}\r\n${headers}\r\n\r\n`
      );

      if (head && head.length) backendSocket.write(head);

      // Pipe both directions
      backendSocket.pipe(socket);
      socket.pipe(backendSocket);
    });

    backendSocket.on('error', (err) => {
      console.error('[WS Proxy] backend error:', err.message);
      socket.destroy();
    });

    socket.on('error', (err) => {
      console.error('[WS Proxy] client error:', err.message);
      backendSocket.destroy();
    });
  });

  server.listen(port, (err) => {
    if (err) throw err;
    console.log(`> Ready on http://localhost:${port}`);
    console.log(`> WebSocket /ws/* proxied to ${backendHost}:${backendPort}`);
  });
});

