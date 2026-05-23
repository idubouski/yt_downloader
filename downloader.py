import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

import yt_dlp

CONFIG_FILE = Path(__file__).with_name("config.json")


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text())
    except json.JSONDecodeError:
        return {}


def _download_dir() -> Path:
    config = load_config()
    path = Path(os.environ.get("DOWNLOAD_FOLDER", config.get("download_folder", "downloads")))
    path.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def _cookie_file(cookies_text: str | None):
    if not cookies_text or not cookies_text.strip():
        yield None
        return
    fd, path = tempfile.mkstemp(suffix=".txt", prefix="ytdl-cookies-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(cookies_text)
        yield path
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def get_video_info(url: str, cookies_text: str | None = None) -> dict:
    with _cookie_file(cookies_text) as cookiefile:
        ydl_opts = {"noplaylist": True, "quiet": True, "no_warnings": True}
        if cookiefile:
            ydl_opts["cookiefile"] = cookiefile
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            resolutions = {
                f["height"]
                for f in info.get("formats", [])
                if f.get("vcodec") != "none" and f.get("height")
            }
            return {
                "title": info.get("title"),
                "resolutions": sorted(resolutions, reverse=True),
                "thumbnail": info.get("thumbnail"),
            }


def download_video(url: str, resolution: str | None = None, cookies_text: str | None = None) -> Path:
    config = load_config()
    target_res = resolution or os.environ.get("DEFAULT_RESOLUTION", config.get("default_resolution", "1080"))
    download_path = _download_dir()
    template = config.get("output_template", "%(title)s.%(ext)s")

    format_string = (
        f"bestvideo[height<={target_res}][ext=mp4]+bestaudio[ext=m4a]/"
        f"best[height<={target_res}][ext=mp4]/"
        f"best[ext=mp4]"
    )

    with _cookie_file(cookies_text) as cookiefile:
        ydl_opts = {
            "format": format_string,
            "merge_output_format": "mp4",
            "outtmpl": str(download_path / template),
            "noplaylist": True,
            "quiet": True,
        }
        if cookiefile:
            ydl_opts["cookiefile"] = cookiefile

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info))
            if path.suffix != ".mp4":
                mp4 = path.with_suffix(".mp4")
                if mp4.exists():
                    return mp4
            return path
