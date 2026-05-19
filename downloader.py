import json
import os
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


def get_video_info(url: str) -> dict:
    ydl_opts = {"noplaylist": True, "quiet": True, "no_warnings": True}
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


def download_video(url: str, resolution: str | None = None) -> Path:
    config = load_config()
    target_res = resolution or os.environ.get("DEFAULT_RESOLUTION", config.get("default_resolution", "1080"))
    download_path = _download_dir()
    template = config.get("output_template", "%(title)s.%(ext)s")

    format_string = (
        f"bestvideo[height<={target_res}][ext=mp4]+bestaudio[ext=m4a]/"
        f"best[height<={target_res}][ext=mp4]/"
        f"best[ext=mp4]"
    )

    ydl_opts = {
        "format": format_string,
        "merge_output_format": "mp4",
        "outtmpl": str(download_path / template),
        "noplaylist": True,
        "quiet": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = Path(ydl.prepare_filename(info))
        if path.suffix != ".mp4":
            mp4 = path.with_suffix(".mp4")
            if mp4.exists():
                return mp4
        return path
