/**
 * server.js —— 零依赖本地服务器
 *  1) 静态托管前端（默认 http://localhost:5173）
 *  2) /api/chat 代理转发到阿里云百炼（DashScope OpenAI 兼容模式），
 *     解决浏览器直连的 CORS 限制，并让 API Key 留在本机。
 *
 * 用法：
 *   node server.js
 *   # 若希望密钥由服务端持有（前端不填 Key），先设置环境变量：
 *   #   Windows PowerShell:  $env:DASHSCOPE_API_KEY="sk-xxx"; node server.js
 *   #   bash:                DASHSCOPE_API_KEY=sk-xxx node server.js
 *   # 然后在页面「模型配置」里把接口地址改为  /api
 */
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || 5173;
const ROOT = __dirname;
const UPSTREAM = process.env.DASHSCOPE_BASE
  || 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions';

const MIME = {
  '.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8',
  '.css':'text/css; charset=utf-8', '.json':'application/json; charset=utf-8',
  '.svg':'image/svg+xml', '.png':'image/png', '.ico':'image/x-icon',
  '.md':'text/markdown; charset=utf-8'
};

function serveStatic(req, res){
  let p = decodeURIComponent(req.url.split('?')[0]);
  if(p === '/') p = '/index.html';
  const file = path.join(ROOT, path.normalize(p).replace(/^([/\\])+/, ''));
  if(!file.startsWith(ROOT)){ res.writeHead(403).end('Forbidden'); return; }
  fs.readFile(file, (err, buf) => {
    if(err){ res.writeHead(404, {'Content-Type':'text/plain; charset=utf-8'}).end('404 Not Found'); return; }
    res.writeHead(200, {'Content-Type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream'});
    res.end(buf);
  });
}

function proxyChat(req, res){
  let body = '';
  req.on('data', c => { body += c; if(body.length > 4e6) req.destroy(); });
  req.on('end', () => {
    const key = (req.headers.authorization || '').replace(/^Bearer\s+/i, '')
      || process.env.DASHSCOPE_API_KEY || '';
    if(!key){
      res.writeHead(401, {'Content-Type':'application/json; charset=utf-8'});
      res.end(JSON.stringify({ error:'缺少 API Key：请在页面「模型配置」中填写，或设置环境变量 DASHSCOPE_API_KEY 后重启服务。' }));
      return;
    }
    const u = new URL(UPSTREAM);
    const r = http.request; // 占位，实际用 https
    const https = require('https');
    const up = https.request({
      hostname:u.hostname, path:u.pathname + u.search, method:'POST',
      headers:{ 'Content-Type':'application/json', 'Authorization':`Bearer ${key}`,
                'Content-Length': Buffer.byteLength(body) }
    }, upRes => {
      res.writeHead(upRes.statusCode, {
        'Content-Type': upRes.headers['content-type'] || 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin':'*'
      });
      upRes.pipe(res);
    });
    up.on('error', e => {
      res.writeHead(502, {'Content-Type':'application/json; charset=utf-8'});
      res.end(JSON.stringify({ error:'上游请求失败：' + e.message }));
    });
    up.end(body);
  });
}

http.createServer((req, res) => {
  if(req.method === 'OPTIONS'){
    res.writeHead(204, {
      'Access-Control-Allow-Origin':'*',
      'Access-Control-Allow-Headers':'Content-Type, Authorization',
      'Access-Control-Allow-Methods':'POST, GET, OPTIONS'
    }).end();
    return;
  }
  if(req.url.startsWith('/api/chat') && req.method === 'POST') return proxyChat(req, res);
  if(req.method === 'GET') return serveStatic(req, res);
  res.writeHead(405).end('Method Not Allowed');
}).listen(PORT, () => {
  console.log(`\n  AI Scientist 原型已启动`);
  console.log(`  ▸ 本地访问： http://localhost:${PORT}`);
  console.log(`  ▸ Qwen 代理： POST /api/chat  ${process.env.DASHSCOPE_API_KEY ? '（已从环境变量读取 API Key）' : '（未设置 DASHSCOPE_API_KEY，将使用前端传入的 Key）'}\n`);
});
