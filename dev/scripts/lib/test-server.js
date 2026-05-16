/**
 * Shared HTTP server helper for Playwright tests.
 *
 * Exports:
 *   startServer(webDir) → Promise<{ server: HttpServer, port: number }>
 *
 * - Serves files from webDir with correct MIME types
 * - Binds to 127.0.0.1 on random available port
 * - Caller must call server.close() after tests
 */

'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css',
  '.js': 'application/javascript',
  '.json': 'application/json',
};

function getMimeType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  return MIME_TYPES[ext] || 'application/octet-stream';
}

function startServer(webDir) {
  const server = http.createServer((req, res) => {
    // Strip query strings and normalize path
    let urlPath = req.url.split('?')[0];
    
    // Security: strip .. to prevent directory traversal
    urlPath = urlPath.replace(/\.\./g, '');
    
    // Decode URL encoding
    try {
      urlPath = decodeURIComponent(urlPath);
    } catch (e) {
      res.statusCode = 400;
      res.setHeader('Content-Type', 'text/plain');
      res.end('Bad request');
      return;
    }
    
    // Default to index.html for root
    if (urlPath === '/' || urlPath === '') {
      urlPath = '/compare.html';
    }
    
    // Ensure path doesn't start with multiple slashes
    urlPath = urlPath.replace(/^\/+/, '/');
    
    const filePath = path.join(webDir, urlPath);
    
    fs.readFile(filePath, (err, data) => {
      if (err) {
        res.statusCode = 404;
        res.setHeader('Content-Type', 'text/plain');
        res.end('Not found: ' + urlPath);
        return;
      }
      
      res.setHeader('Content-Type', getMimeType(filePath));
      res.end(data);
    });
  });
  
  return new Promise(resolve => {
    server.listen(0, '127.0.0.1', () => {
      resolve({ server, port: server.address().port });
    });
  });
}

module.exports = { startServer };
