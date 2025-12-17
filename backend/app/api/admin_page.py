# app/api/admin_page.py

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["admin"])

ADMIN_HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SmartCan Admin Realtime Dashboard (WS)</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; padding: 16px; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
    .badge { padding: 4px 8px; border: 1px solid #ddd; border-radius: 999px; }
    #log { margin-top: 12px; border: 1px solid #ddd; border-radius: 8px; padding: 12px; height: 60vh; overflow: auto; background: #fafafa; }
    pre { margin: 0; white-space: pre-wrap; word-break: break-word; }
    button { padding: 8px 12px; border-radius: 8px; border: 1px solid #ddd; background: white; cursor: pointer; }
    input { padding: 8px 12px; border-radius: 8px; border: 1px solid #ddd; }
  </style>
</head>
<body>
  <h2>SmartCan 관리자 실시간 대시보드 (Option C: REST + WebSocket)</h2>

  <div class="row">
    <span class="badge">WS: <span id="wsStatus">DISCONNECTED</span></span>
    <button id="btnConnect">Connect</button>
    <button id="btnClear">Clear</button>
    <input id="typeFilter" placeholder="type 필터 (예: alarm)" />
  </div>

  <div id="log"><pre id="logPre"></pre></div>

<script>
  let ws = null;
  let keepAliveTimer = null;

  const wsStatus = document.getElementById('wsStatus');
  const logPre = document.getElementById('logPre');
  const typeFilter = document.getElementById('typeFilter');

  function log(obj) {
    const filter = (typeFilter.value || '').trim();
    if (filter && obj && obj.type !== filter) return;

    const line = JSON.stringify(obj, null, 2);
    logPre.textContent = line + "\\n\\n" + logPre.textContent;
  }

  function setStatus(s) {
    wsStatus.textContent = s;
  }

  function startKeepAlive() {
    if (keepAliveTimer) return;
    keepAliveTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
      }
    }, 5000);
  }

  function stopKeepAlive() {
    if (keepAliveTimer) {
      clearInterval(keepAliveTimer);
      keepAliveTimer = null;
    }
  }

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

    const scheme = (location.protocol === 'https:') ? 'wss' : 'ws';
    const url = scheme + '://' + location.host + '/ws/admin';

    ws = new WebSocket(url);

    ws.onopen = () => {
      setStatus('CONNECTED');
      log({type:'client', ts: Date.now(), data:{event:'ws_open', url: url}});
      startKeepAlive();
    };

    ws.onclose = () => {
      setStatus('DISCONNECTED');
      log({type:'client', ts: Date.now(), data:{event:'ws_close'}});
      stopKeepAlive();
    };

    ws.onerror = () => {
      setStatus('ERROR');
      log({type:'client', ts: Date.now(), data:{event:'ws_error'}});
    };

    ws.onmessage = (evt) => {
      try { log(JSON.parse(evt.data)); }
      catch { log({type:'raw', ts: Date.now(), data:{payload: evt.data}}); }
    };
  }

  document.getElementById('btnConnect').onclick = connect;
  document.getElementById('btnClear').onclick = () => { logPre.textContent = ''; };

  // auto connect
  connect();
</script>
</body>
</html>
"""


@router.get("/admin", response_class=HTMLResponse)
def admin_page():
    return ADMIN_HTML
