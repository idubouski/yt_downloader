import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from starlette.background import BackgroundTask

import downloader

app = FastAPI(title="YT Downloader")
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
    input, select, button { width: 100%; padding: 0.5rem; margin-bottom: 0.75rem; font: inherit; }
    button { cursor: pointer; background: #111; color: #fff; border: none; border-radius: 4px; }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    #status { font-size: 0.875rem; color: #555; min-height: 1.25rem; }
    form[hidden] { display: none; }
  </style>
</head>
<body>
  <h1>YT Downloader</h1>
  <label for="url">Video URL</label>
  <input id="url" type="url" placeholder="https://www.youtube.com/watch?v=..." required>
  <button type="button" id="info-btn">Get resolutions</button>
  <form id="dl-form" method="post" action="/download" hidden>
    <label for="resolution">Resolution</label>
    <select id="resolution" name="resolution"></select>
    <input type="hidden" name="url" id="dl-url">
    <button type="submit" id="dl-btn">Download MP4</button>
  </form>
  <p id="status"></p>
  <script>
    const url = document.getElementById('url');
    const status = document.getElementById('status');
    const form = document.getElementById('dl-form');
    const resolution = document.getElementById('resolution');
    const dlUrl = document.getElementById('dl-url');
    const infoBtn = document.getElementById('info-btn');
    const dlBtn = document.getElementById('dl-btn');

    infoBtn.onclick = async () => {
      const u = url.value.trim();
      if (!u) return;
      infoBtn.disabled = true;
      status.textContent = 'Fetching…';
      form.hidden = true;
      try {
        const body = new URLSearchParams({ url: u });
        const res = await fetch('/info', { method: 'POST', body });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed');
        resolution.innerHTML = data.resolutions
          .map(r => `<option value="${r}">${r}p</option>`).join('');
        dlUrl.value = u;
        status.textContent = data.title || 'Ready';
        form.hidden = false;
      } catch (e) {
        status.textContent = e.message;
      } finally {
        infoBtn.disabled = false;
      }
    };

    form.onsubmit = () => {
      dlBtn.disabled = true;
      status.textContent = 'Downloading… (may take a while)';
    };
  </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return INDEX_HTML


@app.post("/info")
async def info(url: str = Form(...)):
    url = url.strip()
    if not url:
        raise HTTPException(400, "URL required")
    try:
        return await asyncio.get_running_loop().run_in_executor(
            _pool, downloader.get_video_info, url
        )
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@app.post("/download")
async def download(url: str = Form(...), resolution: str = Form(...)):
    url = url.strip()
    if not url:
        raise HTTPException(400, "URL required")

    try:
        path: Path = await asyncio.get_running_loop().run_in_executor(
            _pool, downloader.download_video, url, resolution
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
