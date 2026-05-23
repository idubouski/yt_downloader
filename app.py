import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from starlette.background import BackgroundTask

import downloader

ROOT_PATH = os.getenv("ROOT_PATH", "").rstrip("/")

app = FastAPI(title="YT Downloader", root_path=ROOT_PATH)
_pool = ThreadPoolExecutor(max_workers=2)

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>YT Downloader</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; max-width: 32rem; margin: 2rem auto; padding: 0 1rem; }
    h1 { font-size: 1.25rem; margin-bottom: 1rem; }
    label { display: block; font-size: 0.875rem; margin-bottom: 0.25rem; }
    input, select, button, textarea { width: 100%; padding: 0.5rem; margin-bottom: 0.75rem; font: inherit; }
    textarea { font-family: ui-monospace, monospace; font-size: 0.75rem; resize: vertical; }
    button { cursor: pointer; background: #111; color: #fff; border: none; border-radius: 4px; }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    #status { font-size: 0.875rem; color: #555; min-height: 1.25rem; }
    form[hidden] { display: none; }
    details { margin-bottom: 1rem; font-size: 0.875rem; }
    summary { cursor: pointer; padding: 0.25rem 0; user-select: none; }
    .help { color: #555; font-size: 0.8125rem; line-height: 1.5; background: #f5f5f5; padding: 0.75rem; border-radius: 4px; margin: 0.5rem 0; }
    .help ol { margin: 0.25rem 0 0.25rem 1.25rem; padding: 0; }
    .help a { color: #06c; }
    .warn { color: #a40; }
  </style>
</head>
<body>
  <h1>YT Downloader</h1>
  <label for="url">Video URL</label>
  <input id="url" type="url" placeholder="https://www.youtube.com/watch?v=..." required>
  <button type="button" id="info-btn">Get resolutions</button>
  <form id="dl-form" method="post" action="__ROOT__/download" hidden>
    <label for="resolution">Resolution</label>
    <select id="resolution" name="resolution"></select>
    <input type="hidden" name="url" id="dl-url">
    <input type="hidden" name="cookies" id="dl-cookies">
    <button type="submit" id="dl-btn">Download MP4</button>
  </form>
  <p id="status"></p>
  <details id="cookies-panel">
    <summary>Cookies (use if YouTube asks to confirm you're not a bot)</summary>
    <div class="help">
      <ol>
        <li>Install a browser extension that exports cookies in Netscape format, e.g.
          <a href="https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc" target="_blank" rel="noopener">Get cookies.txt LOCALLY</a>
          (Chrome) or
          <a href="https://addons.mozilla.org/firefox/addon/cookies-txt/" target="_blank" rel="noopener">cookies.txt</a>
          (Firefox).</li>
        <li>Open <code>youtube.com</code> while signed in.</li>
        <li>Click the extension → export current site as cookies.txt.</li>
        <li>Open the file and paste its full contents below.</li>
      </ol>
      <p class="warn">These cookies grant access to your YouTube/Google account. Only use this on a trusted network and machine.</p>
    </div>
    <label for="cookies">cookies.txt contents</label>
    <textarea id="cookies" rows="6" placeholder="# Netscape HTTP Cookie File ..." spellcheck="false"></textarea>
    <button type="button" id="cookies-clear" style="background:#666">Clear saved cookies</button>
  </details>
  <script>
    const ROOT = "__ROOT__";
    const COOKIE_KEY = "yt-downloader.cookies";
    const url = document.getElementById('url');
    const status = document.getElementById('status');
    const form = document.getElementById('dl-form');
    const resolution = document.getElementById('resolution');
    const dlUrl = document.getElementById('dl-url');
    const dlCookies = document.getElementById('dl-cookies');
    const infoBtn = document.getElementById('info-btn');
    const dlBtn = document.getElementById('dl-btn');
    const cookies = document.getElementById('cookies');
    const cookiesPanel = document.getElementById('cookies-panel');
    const cookiesClear = document.getElementById('cookies-clear');

    const saved = localStorage.getItem(COOKIE_KEY) || '';
    if (saved) { cookies.value = saved; cookiesPanel.open = true; }
    cookies.addEventListener('input', () => {
      localStorage.setItem(COOKIE_KEY, cookies.value);
    });
    cookiesClear.onclick = () => {
      cookies.value = '';
      localStorage.removeItem(COOKIE_KEY);
    };

    infoBtn.onclick = async () => {
      const u = url.value.trim();
      if (!u) return;
      infoBtn.disabled = true;
      status.textContent = 'Fetching…';
      form.hidden = true;
      try {
        const body = new URLSearchParams({ url: u, cookies: cookies.value });
        const res = await fetch(ROOT + '/info', { method: 'POST', body });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed');
        resolution.innerHTML = data.resolutions
          .map(r => `<option value="${r}">${r}p</option>`).join('');
        dlUrl.value = u;
        dlCookies.value = cookies.value;
        status.textContent = data.title || 'Ready';
        form.hidden = false;
      } catch (e) {
        status.textContent = e.message;
      } finally {
        infoBtn.disabled = false;
      }
    };

    form.onsubmit = () => {
      dlCookies.value = cookies.value;
      dlBtn.disabled = true;
      status.textContent = 'Downloading… (may take a while)';
    };
  </script>
</body>
</html>""".replace("__ROOT__", ROOT_PATH)


@app.get("/", response_class=HTMLResponse)
def index():
    return INDEX_HTML


@app.post("/info")
async def info(url: str = Form(...), cookies: str = Form("")):
    url = url.strip()
    if not url:
        raise HTTPException(400, "URL required")
    try:
        return await asyncio.get_running_loop().run_in_executor(
            _pool, downloader.get_video_info, url, cookies
        )
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@app.post("/download")
async def download(
    url: str = Form(...),
    resolution: str = Form(...),
    cookies: str = Form(""),
):
    url = url.strip()
    if not url:
        raise HTTPException(400, "URL required")

    try:
        path: Path = await asyncio.get_running_loop().run_in_executor(
            _pool, downloader.download_video, url, resolution, cookies
        )
    except Exception as e:
        raise HTTPException(500, str(e)) from e

    if not path.is_file():
        raise HTTPException(500, "Download failed")

    def cleanup():
        try:
            os.remove(path)
        except OSError:
            pass

    return FileResponse(
        path,
        media_type="video/mp4",
        filename=path.name,
        background=BackgroundTask(cleanup),
    )
