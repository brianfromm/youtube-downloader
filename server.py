import logging
import os
import queue
import re
import subprocess  # For manual_combine
import tempfile
import threading
import time
import traceback  # For detailed error logging
import uuid
from contextlib import suppress
from threading import Timer
from urllib.parse import quote

import yt_dlp
from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__)

# --- PO Token / bgutil Configuration ---
# BGUTIL_BASE_URL: URL of the bgutil-ytdlp-pot-provider server for PO token generation
# - Default: http://127.0.0.1:4416 for local development
# - Docker: Set to http://bgutil:4416 via docker-compose.yml environment
BGUTIL_BASE_URL = os.environ.get("BGUTIL_BASE_URL", "http://127.0.0.1:4416")


def get_ytdlp_base_opts():
    """
    Return base yt-dlp options for PO token support and SABR workaround.

    These options enable downloading from videos that enforce SABR streaming by:
    - Using Node.js for JavaScript challenge solving
    - Using the mweb (mobile web) client which works with PO tokens
    - Configuring the bgutil plugin to fetch PO tokens from the bgutil server
    """
    return {
        "js_runtimes": {"node": {}},  # Enable Node.js for JS challenge solving
        "extractor_args": {
            "youtube": {"player_client": ["mweb"]},
            "youtubepot-bgutilhttp": {"base_url": [BGUTIL_BASE_URL]},
        },
    }
CORS(app)
app.logger.propagate = False  # Prevent duplicate logs when using Gunicorn

# Configure logger for direct execution (e.g., `python3 server.py`)
if __name__ == "__main__" and not app.debug:
    # If running directly and not in debug mode, set up a custom stream handler.
    # Flask's default debug logger is used if app.debug is True.
    app.logger.setLevel(logging.DEBUG)
    # It's good practice to clear existing handlers if defining your own from scratch for this scenario.
    # However, Flask might not add handlers until app.run() or if app.debug is true.
    # For safety, clearing can prevent potential duplicates if Flask adds a default non-debug handler early.
    app.logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(process)d - %(threadName)s - %(message)s")
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)

# Configure logger when run with Gunicorn
if __name__ != "__main__":
    # When Gunicorn runs the app, it sets up its own logging.
    # We want app.logger to use Gunicorn's handlers to avoid duplicate messages
    # and ensure logs go to Gunicorn's configured outputs.
    gunicorn_logger = logging.getLogger("gunicorn.error")
    app.logger.handlers.clear()  # Remove any handlers Flask might have set up
    app.logger.handlers.extend(gunicorn_logger.handlers)  # Use Gunicorn's handlers
    app.logger.setLevel(gunicorn_logger.level)
    # app.logger.propagate = False (set earlier) ensures these messages don't also go to root logger.

# Ensure PROCESSED_FILES_DIR exists when module loads
PROCESSED_FILES_DIR = os.path.join(os.getcwd(), "processed_files")  # Define PROCESSED_FILES_DIR before using it
if not os.path.exists(PROCESSED_FILES_DIR):
    print(f"Creating processed files directory: {PROCESSED_FILES_DIR}", flush=True)
    os.makedirs(PROCESSED_FILES_DIR)

app.logger.info("Flask logger initialized.")

# --- Task Queue Setup ---
task_queue = queue.Queue()
task_statuses = {}  # Stores status and result (e.g., filename or error)
COMPLETED_TASKS = {}  # Stores the final state of tasks (completed or failed) for persistent lookup
cancelled_tasks = set()  # Track task IDs that should be cancelled
PROCESSED_FILES_DIR = os.path.join(os.getcwd(), "processed_files")
# --- End Task Queue Setup ---


def clean_filename_for_storage(filename):
    if not filename or filename is None:
        return "video"
    filename = str(filename)
    filename = re.sub(r'[<>:"/\\|?*]', "", filename)
    filename = re.sub(r"_+", " ", filename)
    filename = re.sub(r"\s+", " ", filename)
    filename = filename.strip()
    if len(filename) > 100:
        filename = filename[:100].strip()
    if not filename:
        return "video"
    return filename


def create_descriptive_filename(
    video_title: str, task_id: str, file_extension: str = "mp4", quality_info: str | None = None
) -> str:
    """Create a descriptive filename for storage that includes title and ensures uniqueness"""
    clean_title = clean_filename_for_storage(video_title)

    # Add quality info if provided
    if quality_info:
        clean_title += f" ({quality_info})"

    # Add first 8 characters of UUID for uniqueness while keeping readability
    unique_suffix = task_id[:8]

    # Construct filename: "Title (quality) [uuid8].ext"
    descriptive_filename = f"{clean_title} [{unique_suffix}].{file_extension}"

    # Final safety check on length (filesystem limits)
    if len(descriptive_filename) > 200:
        # Truncate title but keep the unique suffix and extension
        max_title_length = 200 - len(f" [{unique_suffix}].{file_extension}")
        clean_title = clean_title[:max_title_length].strip()
        descriptive_filename = f"{clean_title} [{unique_suffix}].{file_extension}"

    return descriptive_filename


def sanitize_for_http_header(filename):
    if not filename or filename is None:
        return "video"
    filename = str(filename)
    filename = re.sub(r'[\'"]', "", filename)
    filename = filename.strip()
    if not filename:
        return "video"
    return quote(filename.encode("utf-8"), safe=" -.()[]!&")


def cleanup_old_files(max_age_hours: int = 168) -> None:  # 7 days = 168 hours
    """Remove processed files older than max_age_hours"""
    if not os.path.exists(PROCESSED_FILES_DIR):
        app.logger.debug("Processed files directory does not exist, skipping cleanup")
        return

    cutoff_time = time.time() - (max_age_hours * 3600)
    cleaned_count = 0
    total_size_mb = 0

    try:
        for filename in os.listdir(PROCESSED_FILES_DIR):
            filepath = os.path.join(PROCESSED_FILES_DIR, filename)
            try:
                # Check file age (creation time)
                if os.path.getctime(filepath) < cutoff_time:
                    file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
                    os.remove(filepath)
                    app.logger.info(f"🗑️ Cleaned up old file: {filename} ({file_size:.1f} MB)")
                    cleaned_count += 1
                    total_size_mb += file_size
            except Exception as e:
                app.logger.error(f"Error cleaning file {filename}: {e}")

        if cleaned_count > 0:
            app.logger.info(f"🧹 Cleanup complete: removed {cleaned_count} old files, freed {total_size_mb:.1f} MB")
        else:
            app.logger.debug("🧹 Cleanup complete: no old files to remove")

    except Exception as e:
        app.logger.error(f"Error during cleanup process: {e}")


def cleanup_old_tasks(max_age_hours: int = 24) -> None:  # 24 hours = 1 day
    """Remove completed tasks older than max_age_hours from memory"""
    try:
        cutoff_time = time.time() - (max_age_hours * 3600)
        cleaned_count = 0

        # Create a list of task IDs to remove (can't modify dict during iteration)
        tasks_to_remove = []

        for task_id, task_data in COMPLETED_TASKS.items():
            completed_at = task_data.get("completed_at", 0)
            if completed_at and completed_at < cutoff_time:
                tasks_to_remove.append(task_id)

        # Remove old tasks
        for task_id in tasks_to_remove:
            COMPLETED_TASKS.pop(task_id, None)
            task_statuses.pop(task_id, None)
            cleaned_count += 1

        if cleaned_count > 0:
            app.logger.info(f"🧹 Task cleanup complete: removed {cleaned_count} old task records from memory")
        else:
            app.logger.debug("🧹 Task cleanup complete: no old tasks to remove")

    except Exception as e:
        app.logger.error(f"Error during task cleanup process: {e}")


def schedule_cleanup() -> None:
    """Schedule periodic cleanup every 24 hours"""
    app.logger.info("🧹 Starting scheduled cleanup of old processed files and tasks...")
    cleanup_old_files(max_age_hours=168)  # Remove files older than 7 days
    cleanup_old_tasks(max_age_hours=24)  # Remove task records older than 1 day

    # Schedule next cleanup in 24 hours
    Timer(24 * 3600, schedule_cleanup).start()
    app.logger.debug("🔄 Next cleanup scheduled in 24 hours")


def _update_progress(task_id: str, progress_data: dict[str, any], phase: str = "downloading") -> None:
    """Update task progress from yt-dlp progress hooks"""
    try:
        # Check if task has been cancelled - abort download immediately
        if task_id in cancelled_tasks:
            app.logger.info(f"🚫 Task {task_id} cancelled during {phase}, aborting yt-dlp download")
            raise Exception(f"Task {task_id} cancelled by user")

        status = progress_data.get("status")

        if status == "downloading":
            downloaded = progress_data.get("downloaded_bytes", 0)
            total = progress_data.get("total_bytes") or progress_data.get("total_bytes_estimate", 0)
            speed = progress_data.get("speed", 0)
            eta = progress_data.get("eta", 0)

            # Calculate percentage
            progress_percent = 0
            if total and total > 0:
                progress_percent = min(100, (downloaded / total) * 100)

            # Get current status or create new one
            current_status = task_statuses.get(task_id, {})
            current_status.update(
                {
                    "status": "processing",
                    "phase": phase,
                    "progress_percent": round(progress_percent, 1),
                    "downloaded_bytes": downloaded,
                    "total_bytes": total,
                    "speed_bytes_per_sec": speed or 0,
                    "eta_seconds": eta or 0,
                    "message": f"{phase.replace('_', ' ').title()}: {progress_percent:.1f}%",
                }
            )

            task_statuses[task_id] = current_status
            COMPLETED_TASKS[task_id] = current_status

        elif status == "finished":
            current_status = task_statuses.get(task_id, {})
            current_status.update(
                {
                    "status": "processing",
                    "phase": f"{phase}_complete",
                    "progress_percent": 100,
                    "message": f"{phase.replace('_', ' ').title()} complete",
                }
            )
            task_statuses[task_id] = current_status
            COMPLETED_TASKS[task_id] = current_status

    except Exception as e:
        app.logger.error(f"Error updating progress for task {task_id}: {e}")


def _postprocessor_hook(task_id: str, d: dict[str, any]) -> None:
    """Update task status during yt-dlp postprocessing (FFmpeg transcoding)"""
    try:
        status = d.get("status")
        postprocessor = d.get("postprocessor", "")

        if status == "started" and "FFmpeg" in postprocessor:
            # Transcoding phase started
            current_status = task_statuses.get(task_id, {})
            current_status.update(
                {
                    "status": "processing",
                    "phase": "combining",
                    "progress_percent": 0,
                    "message": "Combining video and audio...",
                }
            )
            task_statuses[task_id] = current_status
            COMPLETED_TASKS[task_id] = current_status
            app.logger.info(f"🔄 Task {task_id}: FFmpeg postprocessing started")

    except Exception as e:
        app.logger.error(f"Error in postprocessor hook for task {task_id}: {e}")


def _mp3_postprocessor_hook(task_id: str, d: dict[str, any]) -> None:
    """Update task status during MP3 conversion for UI feedback"""
    try:
        status = d.get("status")
        postprocessor = d.get("postprocessor", "")

        if status == "started" and postprocessor == "ExtractAudio":
            current_status = task_statuses.get(task_id, {})
            current_status.update(
                {
                    "status": "processing",
                    "phase": "converting_mp3",
                    "progress_percent": 100,  # Download complete, conversion starting
                    "message": "Converting to MP3...",
                }
            )
            task_statuses[task_id] = current_status
            COMPLETED_TASKS[task_id] = current_status
            app.logger.info(f"🎵 Task {task_id}: MP3 conversion started")

        elif status == "finished":
            current_status = task_statuses.get(task_id, {})
            current_status.update(
                {
                    "status": "processing",
                    "phase": "converting_mp3_complete",
                    "progress_percent": 95,
                    "message": "MP3 conversion complete",
                }
            )
            task_statuses[task_id] = current_status
            COMPLETED_TASKS[task_id] = current_status
            app.logger.info(f"🎵 Task {task_id}: MP3 conversion finished")

    except Exception as e:
        app.logger.error(f"Error in MP3 postprocessor hook for task {task_id}: {e}")


def _parse_ffmpeg_progress(task_id: str, stderr_line: str, total_duration: float) -> None:
    """Parse FFmpeg stderr output and update task progress"""
    try:
        # Check if task has been cancelled - signal to abort FFmpeg
        if task_id in cancelled_tasks:
            app.logger.info(f"🚫 Task {task_id} cancelled during FFmpeg combine, signaling abort")
            raise Exception(f"Task {task_id} cancelled by user")

        # FFmpeg outputs progress in format: "time=HH:MM:SS.ms ..."
        # Example: "frame=  123 fps= 45 q=28.0 size=    1024kB time=00:00:05.12 bitrate=1638.4kbits/s speed=1.2x"
        if "time=" in stderr_line:
            # Extract time value - flexible regex for various FFmpeg formats
            time_match = re.search(r"time=(\d+):(\d+):(\d+\.?\d*)", stderr_line)
            if time_match and total_duration > 0:
                hours, minutes, seconds = time_match.groups()
                current_time = int(hours) * 3600 + int(minutes) * 60 + float(seconds)

                # Calculate percentage
                progress_percent = min(100, (current_time / total_duration) * 100)

                # Extract speed if available
                speed_match = re.search(r"speed=\s*(\d+\.?\d*)x", stderr_line)
                speed_text = speed_match.group(1) if speed_match else ""

                # Update task status
                current_status = task_statuses.get(task_id, {})
                current_status.update(
                    {
                        "status": "processing",
                        "phase": "combining",
                        "progress_percent": round(progress_percent, 1),
                        "message": f"Combining: {progress_percent:.1f}%" + (f" ({speed_text}x)" if speed_text else ""),
                    }
                )

                task_statuses[task_id] = current_status
                COMPLETED_TASKS[task_id] = current_status

                # Log progress updates every 10% for debugging
                if int(progress_percent) % 10 == 0 or progress_percent >= 99:
                    app.logger.info(f"🎬 Task {task_id}: FFmpeg progress: {progress_percent:.1f}% ({speed_text}x)")

    except Exception as e:
        app.logger.error(f"Error parsing FFmpeg progress for task {task_id}: {e}")
        # Re-raise cancellation exceptions so they propagate to kill the FFmpeg process
        if task_id in cancelled_tasks:
            raise


@app.route("/")
def serve_html():
    try:
        return render_template("youtube-downloader.html")
    except Exception as e:
        app.logger.error(f"Error rendering HTML template: {e!s}")  # For server-side logging
        return f"Error rendering HTML template: {e!s}.", 500  # Send error to client


@app.route("/health")
def health():
    """Health check endpoint for monitoring"""
    try:
        # Check disk space
        stat = os.statvfs(PROCESSED_FILES_DIR if os.path.exists(PROCESSED_FILES_DIR) else "/")
        disk_free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)

        # Check worker thread
        worker_alive = worker_thread.is_alive() if "worker_thread" in globals() else False

        # Check queue size
        queue_size = task_queue.qsize()

        # Count processed files
        processed_files_count = 0
        if os.path.exists(PROCESSED_FILES_DIR):
            processed_files_count = len(
                [f for f in os.listdir(PROCESSED_FILES_DIR) if os.path.isfile(os.path.join(PROCESSED_FILES_DIR, f))]
            )

        health_status = {
            "status": "healthy",
            "queue_size": queue_size,
            "worker_alive": worker_alive,
            "disk_free_gb": round(disk_free_gb, 2),
            "processed_files_count": processed_files_count,
            "uptime_seconds": int(time.time() - app.start_time) if hasattr(app, "start_time") else 0,
        }

        # Determine if unhealthy based on thresholds
        if not worker_alive:
            health_status["status"] = "unhealthy"
            health_status["message"] = "Worker thread is not running"
        elif disk_free_gb < 1:
            health_status["status"] = "warning"
            health_status["message"] = "Low disk space"
        elif queue_size > 100:
            health_status["status"] = "warning"
            health_status["message"] = "Large queue size"

        return jsonify(health_status), 200 if health_status["status"] == "healthy" else 503

    except Exception as e:
        app.logger.error(f"Health check failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


def clean_youtube_url(url):
    video_id_match = re.search(r"(?:youtube\.com\/(?:watch\?v=|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})", url)
    if not video_id_match:
        return url
    video_id = video_id_match.group(1)
    timestamp = None
    try:
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(url)
        if parsed.query:
            params = parse_qs(parsed.query)
            if "t" in params:
                timestamp = params["t"][0]
            elif "start" in params:
                timestamp = params["start"][0]
        if parsed.fragment and parsed.fragment.startswith("t="):
            timestamp = parsed.fragment[2:]
        if "&t=" in url:
            t_match = re.search(r"[&?]t=([^&]+)", url)
            if t_match:
                timestamp = t_match.group(1)
    except Exception:  # Catch all exceptions during timestamp parsing
        pass
    clean_url = f"https://www.youtube.com/watch?v={video_id}"
    if timestamp:
        clean_url += f"&t={timestamp}"
    return clean_url


@app.route("/extract", methods=["POST"])
def extract_video_info():
    try:
        data = request.json
        url = data.get("url")
        if not url:
            return jsonify({"error": "No URL provided"}), 400

        clean_url = clean_youtube_url(url)
        app.logger.info(f"🎬 Extracting from: {clean_url}")
        if clean_url != url:
            app.logger.debug(f"🧹 Cleaned URL from original: {url}")  # Changed to debug, less critical

        ydl_opts = {"quiet": False, "no_warnings": False, "extract_flat": False, "socket_timeout": 300, **get_ytdlp_base_opts()}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)

            # Removed verbose raw format logging block

            video_data = {
                "title": info.get("title", "Unknown"),
                "thumbnail_url": info.get("thumbnail", None),
                "duration": info.get("duration_string", "Unknown"),
                "duration_seconds": info.get("duration", 0),  # Raw duration in seconds for FFmpeg progress
                "uploader": info.get("uploader", "Unknown"),
                "view_count": (f"{info.get('view_count', 0):,}" if info.get("view_count") else "Unknown"),
                "upload_date": info.get("upload_date", "Unknown"),
                "formats": [],
            }
            title_for_log = video_data["title"]
            if len(title_for_log) > 50:
                title_for_log = title_for_log[:47] + "..."
            app.logger.info(f"📝 Processing: \"{title_for_log}\" by {video_data['uploader']}")
            for fmt in info.get("formats", []):
                if fmt.get("url"):
                    format_entry = {
                        "format_id": fmt.get("format_id", ""),
                        "ext": fmt.get("ext", ""),
                        "vcodec": fmt.get("vcodec", "none"),
                        "acodec": fmt.get("acodec", "none"),
                        "url": fmt.get("url", ""),
                        "protocol": fmt.get("protocol", "unknown"),
                        "height": fmt.get("height"),
                        "width": fmt.get("width"),
                        "abr": fmt.get("abr"),
                        "tbr": fmt.get("tbr"),
                        "fps": fmt.get("fps"),
                    }
                    # Skip storyboards early
                    if fmt.get("format_note") == "storyboard" or fmt.get("ext") == "mhtml":
                        continue

                    vcodec_val = format_entry["vcodec"]  # Uses 'none' if original was None/missing
                    acodec_val = format_entry["acodec"]  # Uses 'none' if original was None/missing

                    is_video_stream = vcodec_val != "none" and fmt.get("height") is not None
                    is_audio_stream_explicit = acodec_val != "none"

                    # Infer audio if vcodec is 'none' and it's not a storyboard (already filtered storyboards)
                    # This handles cases where yt-dlp might return acodec as None for an HLS audio stream
                    # (e.g., format 233, 234 in logs)
                    is_inferred_audio = vcodec_val == "none"

                    if is_video_stream and is_audio_stream_explicit:
                        format_entry["type"] = "video+audio"
                        format_entry["quality"] = f"{fmt.get('height')}p"
                    elif is_video_stream:
                        format_entry["type"] = "video-only"
                        format_entry["quality"] = f"{fmt.get('height')}p"
                    elif is_audio_stream_explicit or is_inferred_audio:
                        format_entry["type"] = "audio-only"
                        if format_entry["protocol"] in ["m3u8", "m3u8_native"]:
                            format_entry["ext"] = "m4a"  # Ensure HLS audio is marked for m4a output
                            format_entry["acodec"] = "aac"  # Assume AAC for HLS audio converted to m4a
                        current_abr = fmt.get("abr")
                        current_tbr = fmt.get("tbr")
                        if current_abr:
                            format_entry["quality"] = f"{current_abr:.0f}kbps"
                        elif current_tbr:
                            format_entry["quality"] = f"{current_tbr:.0f}kbps (approx)"
                        else:
                            format_entry["quality"] = fmt.get("format_note", "Audio")

                        # If it's an HLS audio stream, we know we'll convert it to m4a
                        if format_entry["protocol"] in ["m3u8", "m3u8_native"]:
                            app.logger.debug(
                                f"🎧 HLS audio {format_entry['format_id']} detected. Ext: m4a. "
                                f"Original: {format_entry['ext']}"
                            )
                            format_entry["ext"] = "m4a"

                    else:
                        format_entry["type"] = "other"
                        format_entry["quality"] = fmt.get("format_note", "Unknown")

                    # Handle filesize display
                    filesize_bytes = fmt.get("filesize") or fmt.get("filesize_approx")
                    if filesize_bytes:
                        format_entry["filesize"] = f"{filesize_bytes / (1024*1024):.1f} MB"
                    else:
                        format_entry["filesize"] = "N/A"  # Use N/A for unknown or zero size
                    video_data["formats"].append(format_entry)

            video_audio_formats = [f for f in video_data["formats"] if f["type"] == "video+audio"]
            video_only_formats = [f for f in video_data["formats"] if f["type"] == "video-only"]
            audio_only_formats = [f for f in video_data["formats"] if f["type"] == "audio-only"]
            other_formats = [f for f in video_data["formats"] if f["type"] == "other"]

            def sort_by_quality(format_list, is_audio=False):
                def get_quality_number(fmt):
                    if is_audio:
                        # Prioritize 'abr', then 'tbr', then parse 'quality' string as last resort
                        abr = fmt.get("abr")
                        if abr is not None:
                            return int(abr)

                        tbr = fmt.get("tbr")
                        if tbr is not None:
                            return int(tbr)

                        # Fallback to parsing the 'quality' string if ABR/TBR are missing
                        quality_str = fmt.get("quality", "0")
                        match = re.search(r"(\d+)", quality_str.replace("kbps", ""))
                        return int(match.group(1)) if match else 0
                    else:
                        return fmt.get("height", 0) or 0

                return sorted(format_list, key=get_quality_number, reverse=True)

            video_audio_formats = sort_by_quality(video_audio_formats)
            video_only_formats = sort_by_quality(video_only_formats)
            audio_only_formats = sort_by_quality(audio_only_formats, is_audio=True)

            # Add MP3 conversion options if audio formats exist
            if audio_only_formats:
                best_audio = audio_only_formats[0]  # Highest quality audio
                duration_secs = video_data.get("duration_seconds", 0)

                # Add MP3 options at different bitrates
                for mp3_bitrate_kbps in [192, 128]:
                    if duration_secs:
                        estimated_mp3_size_mb = (duration_secs * mp3_bitrate_kbps) / 8 / 1000
                        estimated_size_str = f"{estimated_mp3_size_mb:.1f} MB"
                    else:
                        estimated_size_str = "N/A"
                    mp3_option = {
                        "format_id": f"bestaudio_mp3_{mp3_bitrate_kbps}",  # e.g., bestaudio_mp3_192
                        "ext": "mp3",
                        "type": "audio-only",
                        "quality": f"{mp3_bitrate_kbps}kbps",  # Match format: ###kbps
                        "acodec": "mp3",
                        "abr": mp3_bitrate_kbps,  # For sorting and bitrate detection
                        "protocol": "conversion",
                        "filesize": estimated_size_str,
                        "source_format_id": best_audio.get("format_id"),  # Track source for logging
                    }
                    audio_only_formats.append(mp3_option)

            unique_resolutions = {}
            for fmt in video_only_formats:
                height = fmt.get("height")
                # Add format if height exists and is not already in our collection
                if height and height not in unique_resolutions:
                    unique_resolutions[height] = fmt

            sorted_heights = sorted(unique_resolutions.keys(), reverse=True)
            # Include all unique resolutions 480p and above
            video_only_formats_for_combine = []
            for height in sorted_heights:
                if height >= 480:
                    video_only_formats_for_combine.append(unique_resolutions[height])
            # Removed debug print for video_only_formats_for_combine
            video_only_formats = video_only_formats_for_combine

            video_data["formats"] = video_audio_formats + video_only_formats + audio_only_formats + other_formats
            title_for_log = video_data.get("title", "Unknown Title")
            if len(title_for_log) > 40:
                title_for_log = title_for_log[:37] + "..."
            app.logger.info(f"✅ Extracted {len(video_data['formats'])} formats for \"{title_for_log}\"")
            return jsonify(video_data)

    except Exception as e:
        url_for_log = clean_url if "clean_url" in locals() else "unknown URL"
        app.logger.error(f"❌ Extraction failed for {url_for_log}: {e!s}")
        traceback.print_exc()
        return jsonify({"error": f"Failed to extract video information: {e!s}"}), 500


# Manually download video and audio, then combine with FFmpeg. Called by worker.
def _manual_combine_for_worker(
    task_id,
    clean_url,
    video_format_id,
    audio_format_id,
    clean_title,
    video_resolution,
    temp_dir_path,
    video_duration=0,
):
    """Manually download video and audio, then combine with FFmpeg. Called by worker."""
    app.logger.info(f"🔧 Task {task_id}: Starting manual FFmpeg combine. Temp: {temp_dir_path}")
    start_time = time.time()
    try:
        video_path = os.path.join(temp_dir_path, "video.mp4")  # Use specific extensions if known, otherwise generic
        audio_path = os.path.join(temp_dir_path, "audio.m4a")

        # Determine final output filename for processed files directory
        # Use descriptive filename with title and quality info
        final_disk_filename = create_descriptive_filename(clean_title, task_id, "mp4", video_resolution)
        final_output_path_on_disk = os.path.join(PROCESSED_FILES_DIR, final_disk_filename)

        app.logger.info(f"📝 Task {task_id}: Manual combine target: {final_output_path_on_disk}")

        # Download video stream
        ydl_video_opts = {
            "format": video_format_id,
            "outtmpl": video_path,
            "quiet": True,
            "no_warnings": True,
            "verbose": False,
            "noplaylist": True,
            "progress_hooks": [lambda d: _update_progress(task_id, d, phase="downloading_video")],
            **get_ytdlp_base_opts(),
        }
        with yt_dlp.YoutubeDL(ydl_video_opts) as ydl:
            app.logger.info(f"⏬ Task {task_id}: Downloading video for manual combine...")
            ydl.download([clean_url])
        if not os.path.exists(video_path):
            raise Exception(f"Video download failed for manual combine: {video_path} not found.")
        app.logger.info(f"✅ Task {task_id}: Video download complete: {video_path}")

        # Download audio stream
        ydl_audio_opts = {
            "format": audio_format_id,
            "outtmpl": audio_path,
            "quiet": True,
            "no_warnings": True,
            "verbose": False,
            "noplaylist": True,
            "progress_hooks": [lambda d: _update_progress(task_id, d, phase="downloading_audio")],
            **get_ytdlp_base_opts(),
        }
        with yt_dlp.YoutubeDL(ydl_audio_opts) as ydl:
            app.logger.info(f"⏬ Task {task_id}: Downloading audio for manual combine...")
            ydl.download([clean_url])
        if not os.path.exists(audio_path):
            raise Exception(f"Audio download failed for manual combine: {audio_path} not found.")
        app.logger.info(f"✅ Task {task_id}: Audio download complete: {audio_path}")

        # Update status for combining phase
        current_status = task_statuses.get(task_id, {})
        current_status.update(
            {
                "status": "processing",
                "phase": "combining",
                "progress_percent": 0,
                "message": "Combining video and audio...",
            }
        )
        task_statuses[task_id] = current_status
        COMPLETED_TASKS[task_id] = current_status

        # Combine with ffmpeg, ensuring H.264/AAC for MP4 compatibility
        app.logger.info(f"⚙️ Task {task_id}: Combining with ffmpeg into {final_output_path_on_disk}")
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",  # Overwrite output files without asking
            "-i",
            video_path,
            "-i",
            audio_path,
            "-c:v",
            "libx264",  # Transcode video to H.264
            "-c:a",
            "aac",  # Transcode audio to AAC
            "-strict",
            "-2",  # For experimental AAC codec if needed (often good practice)
            "-crf",
            "23",  # Video quality (Constant Rate Factor, lower is better, 18-28 is typical)
            "-preset",
            "fast",  # Encoding speed (ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow)
            final_output_path_on_disk,  # Output to UUID.mp4
        ]
        # app.logger.info(f"Task {task_id}: Executing FFmpeg command: {' '.join(ffmpeg_cmd)}") # Removed for brevity

        # Execute FFmpeg with real-time progress parsing
        process = subprocess.Popen(
            ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, bufsize=1
        )

        # Read stderr line by line for progress updates
        stderr_output = []
        try:
            for line in process.stderr:
                stderr_output.append(line)
                # Parse progress if we have duration (will raise exception if cancelled)
                if video_duration > 0:
                    _parse_ffmpeg_progress(task_id, line, video_duration)

            # Wait for process to complete
            process.wait()
        except Exception:
            # Task was cancelled - kill FFmpeg process immediately
            if task_id in cancelled_tasks:
                app.logger.info(f"🚫 Task {task_id}: Killing FFmpeg process due to cancellation")
                process.kill()
                process.wait()  # Wait for process to actually terminate
                cancelled_tasks.discard(task_id)  # Remove from cancelled set
                raise  # Re-raise to propagate cancellation
            else:
                # Some other error during progress parsing
                raise

        if process.returncode != 0:
            stderr_text = "".join(stderr_output)
            stderr_summary = stderr_text[:100]  # Truncate stderr for log
            error_message = f"❌ FFmpeg task {task_id} failed. RC: {process.returncode}. Stderr: {stderr_summary}..."
            app.logger.error(error_message)
            raise Exception(error_message)

        total_time = time.time() - start_time
        file_size_mb = os.path.getsize(final_output_path_on_disk) / (1024 * 1024)
        app.logger.info(
            f"Task {task_id}: ✅ Manual FFmpeg combination successful. "
            f"Output: {final_disk_filename}, Size: {file_size_mb:.1f} MB, "
            f"Time: {total_time:.1f}s"
        )
        return final_disk_filename  # Return the actual filename created

    except Exception as e:
        app.logger.error(f"❌ Task {task_id}: Manual FFmpeg combine failed: {e!s}")
        traceback.print_exc()
        raise  # Re-raise to be caught by the calling function in _perform_combination_task


# --- Task Processing Logic ---
# Note: _perform_combination_task was formerly _perform_actual_combination


def _perform_combination_task(task_details):  # Renamed from _perform_actual_combination
    # [Original _perform_combination_task logic starts here...]
    task_id = task_details["task_id"]
    url = task_details["url"]
    video_format_id = task_details["video_format_id"]
    audio_format_id = task_details["audio_format_id"]
    # Define clean_title for logging and user-facing filename
    raw_title = task_details.get("video_title", "video")
    clean_title = clean_filename_for_storage(raw_title)
    # Define video_resolution_text for logging and user-facing filename
    video_resolution_text = task_details.get("video_resolution", "")  # This is the string like '1080p'
    # video_vcodec = task_details.get("video_vcodec") # Now part of video_format_details
    video_duration = task_details.get("video_duration", 0)  # Duration in seconds for FFmpeg progress

    # Get full format details passed from the queue
    video_format_details = task_details.get("video_format_details", {})
    audio_format_details = task_details.get("audio_format_details", {})

    # For logging purposes, get vcodec. The more detailed check happens later.
    log_video_vcodec = video_format_details.get("vcodec", "unknown")

    # 'video_resolution' (from old line 466) and 'submitted_at' (old line 468) were unused.

    app.logger.info(
        f"🚀 Combine task {task_id} for '{clean_title}' ({video_resolution_text}). "
        f"V: {video_format_id}, A: {audio_format_id}, Codec: {log_video_vcodec}"
    )
    processing_status = {
        "status": "processing",
        "message": f"Combining formats for {clean_title}...",
    }
    task_statuses[task_id] = processing_status
    COMPLETED_TASKS[task_id] = processing_status

    # --- Filename for disk storage (descriptive with uniqueness) ---
    # Create descriptive filename that includes title and quality info
    on_disk_filename = create_descriptive_filename(clean_title, task_id, "mp4", video_resolution_text)
    final_output_path = os.path.join(PROCESSED_FILES_DIR, on_disk_filename)

    # --- User-facing filename (descriptive) ---
    user_facing_filename = f"{clean_title}"
    if video_resolution_text:
        user_facing_filename += f" ({video_resolution_text})"
    user_facing_filename += ".mp4"

    app.logger.info(f"📝 Task {task_id}: Output: {final_output_path}, User file: {user_facing_filename}")

    # Clean URL once for all paths
    clean_url = clean_youtube_url(url)

    # Attempt 1: yt-dlp direct merge (fastest if codecs are compatible)
    try:
        # Determine if formats are compatible for direct merge (H.264 video, AAC audio, MP4/M4A container)
        compatible_for_direct_merge = False
        video_vcodec = video_format_details.get("vcodec", "")
        video_ext = video_format_details.get("ext", "")
        audio_acodec = audio_format_details.get("acodec", "")
        audio_ext = audio_format_details.get("ext", "")

        is_video_compatible = video_vcodec and video_vcodec.startswith("avc1") and video_ext == "mp4"
        is_audio_compatible = (
            audio_acodec
            and (audio_acodec == "aac" or audio_acodec.startswith("mp4a"))
            and (audio_ext == "m4a" or audio_ext == "mp4")
        )

        if is_video_compatible and is_audio_compatible:
            compatible_for_direct_merge = True
            app.logger.info(
                f"✅ Task {task_id}: Formats compatible for direct merge. "
                f"Video: {video_vcodec} ({video_ext}), Audio: {audio_acodec} ({audio_ext})."
            )
        else:
            # Transcoding required - use manual combine for progress tracking
            app.logger.info(
                f"🔄 Task {task_id}: Formats require transcoding. "
                f"Video: {video_vcodec} ({video_ext}), Audio: {audio_acodec} ({audio_ext}). "
                f"Using manual combine for FFmpeg progress tracking."
            )
            raise Exception("Transcoding required, skipping yt-dlp direct merge for progress tracking")

        if compatible_for_direct_merge:
            ydl_opts_combine = {
                "format": f"{video_format_id}+{audio_format_id}",
                "merge_output_format": "mp4",
                "outtmpl": final_output_path,
                "verbose": False,
                "quiet": True,
                "noprogress": True,
                "noplaylist": True,
                "ignoreerrors": False,  # Let it fail to trigger manual fallback if direct merge fails
                "socket_timeout": 300,
                "progress_hooks": [lambda d: _update_progress(task_id, d, phase="downloading_combined")],
                **get_ytdlp_base_opts(),
            }
        else:
            ydl_opts_combine = {
                "format": f"{video_format_id}+{audio_format_id}",
                "merge_output_format": "mp4",
                "outtmpl": final_output_path,  # Disk filename: UUID.mp4
                "recodevideo": "mp4",
                "verbose": False,
                "quiet": True,
                "noprogress": True,
                "noplaylist": True,
                "postprocessor_args": ["-vcodec", "libx264", "-acodec", "aac"],
                "ignoreerrors": False,  # Let it fail to trigger manual fallback
                "socket_timeout": 300,
                "progress_hooks": [lambda d: _update_progress(task_id, d, phase="downloading_combined")],
                "postprocessor_hooks": [lambda d: _postprocessor_hook(task_id, d)],
                **get_ytdlp_base_opts(),
            }
        # app.logger.info(f"Task {task_id}: Using yt-dlp opts: {ydl_opts_combine}") # Removed for brevity

        with yt_dlp.YoutubeDL(ydl_opts_combine) as ydl:
            ydl.download([clean_url])

        # If download completes without error, this path is taken by 'else' block.

    except Exception as e_yt_dlp_combine:  # yt-dlp direct merge failed or cancelled
        # Check if task was cancelled
        if "cancelled by user" in str(e_yt_dlp_combine):
            app.logger.info(f"🚫 Task {task_id}: yt-dlp download cancelled, stopping processing")
            cancelled_tasks.discard(task_id)  # Clean up cancelled set
            return  # Exit early, status already set to "cancelled"

        app.logger.warning(f"⚠️ yt-dlp merge failed for task {task_id}: {e_yt_dlp_combine!s}. Falling back to manual.")

        # Attempt 2: Manual download and ffmpeg combination (with transcoding)
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # _manual_combine_for_worker saves as task_id.mp4 and returns task_id (UUID)
                # This function inherently transcodes to H.264/AAC.
                returned_base = _manual_combine_for_worker(
                    task_id,
                    clean_url,
                    video_format_id,
                    audio_format_id,
                    clean_title,
                    video_resolution_text,
                    temp_dir,
                    video_duration,
                )

                # Expected path after manual combine
                actual_created_filepath = os.path.join(PROCESSED_FILES_DIR, returned_base)

                if returned_base == on_disk_filename and os.path.exists(actual_created_filepath):
                    app.logger.info(f"✅ Manual combine task {task_id} success. File: {actual_created_filepath}")
                    success_status = {
                        "status": "completed",
                        "on_disk_filename": on_disk_filename,
                        "filename": user_facing_filename,
                        "message": "File ready for download (manual combine/transcode).",
                        "completed_at": time.time(),
                    }
                    task_statuses[task_id] = success_status
                    COMPLETED_TASKS[task_id] = success_status
                else:
                    # This indicates an issue with _manual_combine_for_worker's output or file saving
                    app.logger.error(
                        f"❌ Manual combine task {task_id} error. Worker: '{returned_base}', "
                        f"Expected: '{actual_created_filepath}' "
                        f"(Exists: {os.path.exists(actual_created_filepath)})."
                    )
                    raise Exception("Manual combine error: Output file not found or worker return mismatch.")

        except Exception as e_manual_combine:  # Manual ffmpeg combination also failed or cancelled
            # Check if task was cancelled
            if "cancelled by user" in str(e_manual_combine):
                app.logger.info(f"🚫 Task {task_id}: Manual combine cancelled, stopping processing")
                cancelled_tasks.discard(task_id)  # Clean up cancelled set
                return  # Exit early, status already set to "cancelled"

            app.logger.error(f"❌ Manual combine task {task_id} also failed: {e_manual_combine!s}")
            traceback.print_exc()

            # Provide user-friendly error messages for common issues
            error_str = str(e_manual_combine)
            if "403" in error_str or "Forbidden" in error_str:
                user_message = "Download URLs expired. Please paste the URL again to get fresh formats."
            elif "404" in error_str or "Not Found" in error_str:
                user_message = "Video not found or unavailable. Please check the URL."
            else:
                user_message = f"Combination failed: {e_manual_combine!s}"

            failure_status = {
                "status": "failed",
                "message": user_message,
                "completed_at": time.time(),
            }
            task_statuses[task_id] = failure_status
            COMPLETED_TASKS[task_id] = failure_status

    else:  # yt-dlp direct merge was successful (no exception from the first 'try' block)
        app.logger.info(f"✅ yt-dlp direct merge task {task_id} success. File: {final_output_path}")
        if not os.path.exists(final_output_path):
            app.logger.error(f"❌ yt-dlp merge task {task_id} success, but file '{final_output_path}' missing!")
            # This should ideally not happen if ydl.download() didn't raise an error.
            # Handling it defensively.
            failure_status = {
                "status": "failed",
                "message": "Combination product missing after reported success.",
                "completed_at": time.time(),
            }
            task_statuses[task_id] = failure_status
            COMPLETED_TASKS[task_id] = failure_status
        else:
            success_status = {
                "status": "completed",
                "on_disk_filename": on_disk_filename,
                "filename": user_facing_filename,  # User-friendly name
                "message": "File ready for download (direct merge).",
                "completed_at": time.time(),
            }
            task_statuses[task_id] = success_status
            COMPLETED_TASKS[task_id] = success_status


def _perform_individual_download(task_details):
    task_id = task_details.get("task_id")
    video_url = clean_youtube_url(task_details.get("url"))  # Clean playlist params from URL
    format_id = task_details.get("format_id")
    # 'selected_format' now comes from 'selected_format_details' passed by queue_individual_download_task
    selected_format = task_details.get("selected_format")
    video_title = task_details.get("video_title", "video")

    if not task_id or not video_url or not format_id or not selected_format or not video_title:
        error_msg = f"❌ Task {task_id or 'Unknown'}: Missing critical details for individual download."
        app.logger.error(error_msg)
        if task_id:  # Update status if task_id is available
            task_statuses[task_id] = {
                "status": "failed",
                "message": "Critical task details missing.",
                "completed_at": time.time(),
            }
            COMPLETED_TASKS[task_id] = task_statuses[task_id]
        return  # Cannot proceed

    app.logger.info(f"📥 Ind. task {task_id} for format {format_id} ('{video_title}') URL: {video_url}")
    # Initialize status
    task_statuses[task_id] = {"status": "processing", "message": "Download initiated."}
    COMPLETED_TASKS[task_id] = task_statuses[task_id]  # Ensure visibility

    files_to_potentially_clean = []

    try:
        clean_title_for_storage = clean_filename_for_storage(video_title)

        resolution_text = ""
        if selected_format.get("height"):
            resolution_text = f"({selected_format.get('height')}p)"
        elif selected_format.get("abr"):
            abr_val = selected_format.get("abr")
            if isinstance(abr_val, (int, float)):
                resolution_text = f"({abr_val:.0f}kbps)"
            else:
                resolution_text = f"({abr_val!s})" if abr_val else "(audio)"  # Handle None or string for ABR

        # Check for MP3 conversion format (e.g., bestaudio_mp3_192, bestaudio_mp3_128)
        is_mp3_conversion = format_id.startswith("bestaudio_mp3")

        # MEMORY d86a8376-601a-403f-a4e7-76e8b4c8916e
        is_hls_audio_only = selected_format.get("type") == "audio-only" and selected_format.get("protocol") in [
            "m3u8",
            "m3u8_native",
        ]

        # Determine final file extension
        if is_mp3_conversion:
            final_file_ext = "mp3"
            resolution_text = "(MP3)"  # Override resolution text for MP3
        elif is_hls_audio_only:
            final_file_ext = "m4a"
        else:
            final_file_ext = selected_format.get("ext", "mp4")

        user_facing_filename_base = (
            f"{clean_title_for_storage} {resolution_text}" if resolution_text else clean_title_for_storage
        )
        user_facing_filename = f"{user_facing_filename_base}.{final_file_ext}"

        # Create descriptive filename for individual downloads
        on_disk_filename_final_target = create_descriptive_filename(
            clean_title_for_storage, task_id, final_file_ext, resolution_text.strip("()")
        )
        on_disk_filepath_final_target = os.path.join(PROCESSED_FILES_DIR, on_disk_filename_final_target)
        files_to_potentially_clean.append(on_disk_filepath_final_target)

        on_disk_filename_pp_double_ext = None
        on_disk_filepath_pp_double_ext = None
        if is_hls_audio_only:  # Only relevant for HLS audio transcoding potentially creating .m4a.m4a
            on_disk_filename_pp_double_ext = f"{on_disk_filename_final_target}.{final_file_ext}"
            on_disk_filepath_pp_double_ext = os.path.join(PROCESSED_FILES_DIR, on_disk_filename_pp_double_ext)
            # files_to_potentially_clean.append(on_disk_filepath_pp_double_ext) # Add only if it's created and different

        # For MP3 conversion, use "bestaudio" format selector; otherwise use the specified format_id
        ydl_format = "bestaudio" if is_mp3_conversion else format_id

        # For MP3 conversion, use outtmpl WITHOUT extension - postprocessor adds .mp3
        if is_mp3_conversion:
            # Strip the .mp3 extension from the output path for yt-dlp
            outtmpl_path = on_disk_filepath_final_target.rsplit(".mp3", 1)[0]
        else:
            outtmpl_path = on_disk_filepath_final_target

        ydl_opts = {
            "format": ydl_format,
            "outtmpl": outtmpl_path,  # yt-dlp will download to this path
            "quiet": True,
            "no_warnings": True,
            "verbose": False,
            "overwrites": True,
            "noplaylist": True,
            "socket_timeout": 300,
            "progress_hooks": [lambda d: _update_progress(task_id, d, phase="downloading")],
            **get_ytdlp_base_opts(),
        }

        ydl_postprocessors = []

        # Add MP3 conversion postprocessor
        if is_mp3_conversion:
            # Get bitrate from selected_format (e.g., 192 or 128)
            mp3_bitrate = str(int(selected_format.get("abr", 192)))
            app.logger.info(f"🎵 Task {task_id}: MP3 conversion requested at {mp3_bitrate}kbps. Downloading best audio and converting.")
            ydl_postprocessors.append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": mp3_bitrate,
                }
            )
        elif is_hls_audio_only:
            app.logger.info(f"🎧 Task {task_id}: HLS audio format {format_id}. Applying FFmpegExtractAudio.")
            ydl_postprocessors.append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",  # Target m4a container with AAC audio
                    "preferredquality": "0",  # Best quality AAC
                }
            )

        if ydl_postprocessors:
            ydl_opts["postprocessors"] = ydl_postprocessors
            # Add postprocessor hook for MP3 conversion UI feedback
            if is_mp3_conversion:
                ydl_opts["postprocessor_hooks"] = [lambda d: _mp3_postprocessor_hook(task_id, d)]

        app.logger.info(
            f"⏬ Task {task_id}: Downloading fmt {ydl_format}. URL: {video_url}, Target: {on_disk_filepath_final_target}"
        )
        # app.logger.debug(f"Task {task_id}: yt-dlp options: {ydl_opts}") # Removed for brevity

        with yt_dlp.YoutubeDL(ydl_opts) as ydl_downloader:
            ydl_downloader.download([video_url])  # yt-dlp uses the main video URL to fetch the specific format

        # After download, check for the double-extension file if HLS audio was processed
        if (
            is_hls_audio_only
            and on_disk_filepath_pp_double_ext
            and os.path.exists(on_disk_filepath_pp_double_ext)
            and on_disk_filepath_pp_double_ext != on_disk_filepath_final_target  # Make sure they are different files
        ):
            app.logger.info(f"📝 Task {task_id}: HLS audio created double-ext file: {on_disk_filepath_pp_double_ext}.")
            # Add the double-extension file to cleanup list as it's an intermediate
            if on_disk_filepath_pp_double_ext not in files_to_potentially_clean:
                files_to_potentially_clean.append(on_disk_filepath_pp_double_ext)

            # The original target (e.g., uuid.m4a) might have been deleted by yt-dlp's postprocessor,
            # or it might be an empty/incomplete file.
            # We want to rename the double-extension file (e.g., uuid.m4a.m4a) to the desired final name (uuid.m4a).
            if os.path.exists(on_disk_filepath_final_target):
                app.logger.warning(
                    f"⚠️ Task {task_id}: Original target {on_disk_filepath_final_target} exists "
                    f"with double-ext. Removing."
                )
                with suppress(Exception):
                    os.remove(on_disk_filepath_final_target)

            app.logger.info(f"📝 Task {task_id}: Renaming {on_disk_filepath_pp_double_ext} to target.")
            os.rename(on_disk_filepath_pp_double_ext, on_disk_filepath_final_target)

        if not os.path.exists(on_disk_filepath_final_target):
            app.logger.error(f"❌ Task {task_id}: Download failed. File {on_disk_filepath_final_target} not found.")
            # Log if double-extension file exists, indicating a rename issue or intended output not handled
            if on_disk_filepath_pp_double_ext and os.path.exists(on_disk_filepath_pp_double_ext):
                app.logger.warning(
                    f"⚠️ Task {task_id}: Double-ext file {on_disk_filepath_pp_double_ext} still exists (rename issue)."
                )
            raise RuntimeError("File not found after download process.")

        app.logger.info(
            f"✅ Task {task_id}: Download successful. "
            f"File: {on_disk_filepath_final_target}. "
            f"User: {user_facing_filename}"
        )
        # Update status for success
        current_task_status = task_statuses.get(task_id, {})  # Get existing status
        current_task_status.update(
            {
                "status": "completed",
                "message": "Download successful.",
                "filename": user_facing_filename,
                "on_disk_filename": on_disk_filename_final_target,
                "completed_at": time.time(),
            }
        )
        task_statuses[task_id] = current_task_status  # Assign the fully updated dict
        COMPLETED_TASKS[task_id] = current_task_status  # Assign the same fully updated dict

    except Exception as e:
        # Check if task was cancelled
        if "cancelled by user" in str(e):
            app.logger.info(f"🚫 Task {task_id}: Individual download cancelled, stopping processing")
            cancelled_tasks.discard(task_id)  # Clean up cancelled set
            return  # Exit early, status already set to "cancelled"

        app.logger.error(f"❌ Task {task_id}: Error in _perform_individual_download: {e!s}")
        if app.debug:  # Print full traceback if in debug mode
            traceback.print_exc()

        # Provide user-friendly error messages for common issues
        error_str = str(e)
        if "403" in error_str or "Forbidden" in error_str:
            user_message = "Download URLs expired. Please paste the URL again to get fresh formats."
        elif "404" in error_str or "Not Found" in error_str:
            user_message = "Video not found or unavailable. Please check the URL."
        else:
            user_message = f"Download failed: {e!s}"

        # Update status for failure
        current_status = task_statuses.get(task_id, {})  # Get current status to preserve any existing fields
        current_status.update(
            {
                "status": "failed",
                "message": user_message,
                "completed_at": time.time(),
            }
        )
        task_statuses[task_id] = current_status
        COMPLETED_TASKS[task_id] = task_statuses[task_id]  # Ensure it's in COMPLETED_TASKS
    finally:
        # Cleanup logic
        final_product_on_disk_name = task_statuses.get(task_id, {}).get("on_disk_filename")
        final_product_full_path = None
        if final_product_on_disk_name:
            final_product_full_path = os.path.join(PROCESSED_FILES_DIR, final_product_on_disk_name)

        unique_files_to_clean = set(files_to_potentially_clean)  # Use set to avoid duplicate cleaning attempts

        for f_path_to_clean in unique_files_to_clean:
            if f_path_to_clean and os.path.exists(f_path_to_clean):
                # Do not delete the final successfully processed file
                if (
                    task_statuses.get(task_id, {}).get("status") == "completed"
                    and f_path_to_clean == final_product_full_path
                ):
                    app.logger.info(f"👍 Task {task_id}: Keeping product: {f_path_to_clean}")
                    continue

                # Otherwise, it's an intermediate, failed, or redundant file, so clean it
                try:
                    os.remove(f_path_to_clean)
                    app.logger.info(f"🗑️ Task {task_id}: Cleaned temp: {f_path_to_clean}")
                except Exception as e_cleanup:
                    app.logger.error(f"🔥 Task {task_id}: Error cleaning {f_path_to_clean}: {e_cleanup!s}")
        app.logger.info(f"🏁 Ind. task {task_id} ended with status: {task_statuses.get(task_id, {}).get('status')}")


# This function is called by the worker to dispatch tasks
def _process_task(task_details):
    task_id = task_details.get("task_id", "unknown_task_id")
    task_type = task_details.get("type")
    app.logger.info(f"⚙️ Processing task {task_id} of type {task_type}")

    # Check if task has been cancelled
    if task_id in cancelled_tasks:
        app.logger.info(f"🚫 Task {task_id} was cancelled, skipping processing")
        cancelled_tasks.discard(task_id)  # Remove from cancelled set
        return

    if task_type == "combination":
        _perform_combination_task(task_details)
    elif task_type == "individual_download":
        _perform_individual_download(task_details)  # Assuming this function is defined elsewhere
    else:
        app.logger.error(f"❌ Task {task_id}: Unknown task type '{task_type}'. Marking as failed.")
        failure_status = {
            "status": "failed",
            "message": f"Unknown task type: {task_type}",
            "completed_at": time.time(),
        }
        # Ensure task_statuses and COMPLETED_TASKS are accessible here or passed if necessary
        # For now, assuming they are global as per previous structure
        task_statuses[task_id] = failure_status
        COMPLETED_TASKS[task_id] = failure_status


def combination_worker_loop():
    print("🛠️ Combination worker thread started.", flush=True)
    while True:
        try:
            task_details = task_queue.get()
            task_id = task_details["task_id"]
            app.logger.info(f"👷 Worker picked up task: {task_id} with details: {task_details}")
            _process_task(task_details)
            task_queue.task_done()
            app.logger.info(f"✅ Worker finished task: {task_id}")
        except Exception as e:
            task_id_in_error = (
                task_details.get("task_id", "unknown_task") if "task_details" in locals() else "unknown_task"
            )
            app.logger.error(
                f"💥 Critical error in worker loop for task {task_id_in_error}: {e}",
                exc_info=True,
            )
            if task_id_in_error != "unknown_task":
                current_status = COMPLETED_TASKS.get(task_id_in_error, {})
                if current_status.get("status") not in ["completed", "failed"]:
                    failure_status = {
                        "status": "failed",
                        "message": f"Critical worker error: {e!s}",
                        "completed_at": time.time(),
                    }
                    task_statuses[task_id_in_error] = failure_status  # Update live status
                    COMPLETED_TASKS[task_id_in_error] = failure_status  # Update persistent record
            if "task_details" in locals() and hasattr(task_queue, "task_done"):  # Ensure task_done can be called
                task_queue.task_done()


@app.route("/combine", methods=["POST"])
def combine_video_audio_queued():
    try:
        data = request.json
        url = data.get("url")
        video_title = data.get("videoTitle", "video")
        video_duration = data.get("videoDuration", 0)

        # Get full format details sent from the frontend
        video_format_details = data.get("video_format_details")
        audio_format_details = data.get("audio_format_details")

        if not video_format_details or not audio_format_details:
            return (
                jsonify({"error": "video_format_details and audio_format_details are required."}),
                400,
            )

        # Extract IDs from the details objects
        video_format_id = video_format_details.get("format_id")
        audio_format_id = audio_format_details.get("format_id")

        # Extract other relevant info, preferring details from the format objects
        # Fallback to older direct parameters if needed, though ideally they become redundant
        raw_video_resolution = video_format_details.get("quality") or video_format_details.get("height")
        if isinstance(raw_video_resolution, int):  # if it's height like 1080
            raw_video_resolution = f"{raw_video_resolution}p"
        elif not isinstance(raw_video_resolution, str):  # Ensure it's a string or empty
            raw_video_resolution = data.get("videoResolution", "")  # Fallback to explicitly passed param

        video_vcodec = video_format_details.get("vcodec") or data.get("videoVcodec")

        # Clean up video_resolution if it's problematic (e.g. 'nullp', 'undefinedp', or just 'p')
        video_resolution = ""
        if (
            raw_video_resolution
            and isinstance(raw_video_resolution, str)
            and raw_video_resolution.lower() not in ["nullp", "undefinedp", "p", "unknown"]
        ):
            video_resolution = raw_video_resolution.replace(
                "p", ""
            )  # Store just the number like '1080' or keep as is if it's already '1080p'
            if video_resolution.isdigit():  # Ensure it's a number before adding 'p'
                video_resolution = f"{video_resolution}p"
            else:  # if it was something else, or became empty after stripping 'p'
                video_resolution = (
                    raw_video_resolution if raw_video_resolution.endswith("p") else ""
                )  # keep original if it ended with p, else empty
        if not video_resolution:  # final fallback
            video_resolution = ""  # Use empty string for no resolution

        if not all([url, video_format_id, audio_format_id]):
            return (
                jsonify({"error": "URL, video_format_id, and audio_format_id required"}),
                400,
            )

        video_format_id = str(video_format_id).split("-")[0]
        audio_format_id = str(audio_format_id).split("-")[0]

        task_id = str(uuid.uuid4())
        task_details = {
            "task_id": task_id,
            "url": url,
            "video_format_id": video_format_id,
            "audio_format_id": audio_format_id,
            "video_title": video_title,
            "video_duration": video_duration,  # Duration in seconds for FFmpeg progress
            "video_resolution": video_resolution,  # Pass the cleaned resolution string
            "video_vcodec": video_vcodec,  # Pass the video codec
            "video_format_details": video_format_details,  # Pass full video format details
            "audio_format_details": audio_format_details,  # Pass full audio format details
            "submitted_at": time.time(),
            "type": "combination",  # Specify task type
        }

        task_queue.put(task_details)
        task_statuses[task_id] = {
            "status": "queued",
            "message": "Request accepted and queued for processing.",
        }

        app.logger.info(f"📨 Task {task_id} (combination) queued for URL: {url}")

        status_check_url = f"/task_status/{task_id}"  # Relative URL
        return (
            jsonify(
                {
                    "message": "Request accepted and queued for processing.",
                    "task_id": task_id,
                    "status_url": status_check_url,
                }
            ),
            202,
        )  # HTTP 202 Accepted

    except Exception as e:
        # print(f"❌ Error queueing combination task: {e!s}", flush=True) # Removed, traceback is kept
        app.logger.error(f"❌ Error queueing combination task for {url if 'url' in locals() else 'unknown URL'}: {e!s}")
        traceback.print_exc()
        return jsonify({"error": f"Error queueing task: {e!s}"}), 500


@app.route("/queue_individual_download", methods=["POST"])
def queue_individual_download_task():
    try:
        data = request.json
        url = data.get("url")  # Original YouTube URL
        format_id = data.get("format_id")
        selected_format_details = data.get("selected_format_details")  # Dict of format details
        video_title = data.get("video_title", "video")

        if not all([url, format_id, selected_format_details, video_title]):
            return (
                jsonify({"error": "URL, format_id, selected_format_details, and video_title required"}),
                400,
            )

        task_id = str(uuid.uuid4())
        task_details = {
            "task_id": task_id,
            "type": "individual_download",
            "url": url,
            "format_id": format_id,
            "selected_format": selected_format_details,  # Pass the whole dict
            "video_title": video_title,
            "submitted_at": time.time(),
        }

        task_queue.put(task_details)
        task_statuses[task_id] = {
            "status": "queued",
            "message": "Individual download accepted and queued.",
        }
        COMPLETED_TASKS[task_id] = task_statuses[task_id]  # Initialize for polling

        app.logger.info(f"+ Queued ind. task {task_id} for URL: {url}, fmt: {format_id}")

        status_check_url = f"/task_status/{task_id}"
        return (
            jsonify(
                {
                    "message": "Individual download request accepted and queued.",
                    "task_id": task_id,
                    "status_url": status_check_url,
                }
            ),
            202,
        )

    except Exception as e:
        format_id_str = format_id if "format_id" in locals() else "unknown"
        url_str = url if "url" in locals() else "unknown URL"
        app.logger.error(f"❌ Error queueing ind. download for {url_str} (fmt: {format_id_str}): {e!s}")
        traceback.print_exc()
        return jsonify({"error": f"Error queueing individual download: {e!s}"}), 500


@app.route("/task_status/<task_id>", methods=["GET"])
def get_task_status(task_id):
    status_info = task_statuses.get(task_id)
    if not status_info:
        return jsonify({"error": "Task ID not found"}), 404
    return jsonify(status_info), 200


@app.route("/cancel_task/<task_id>", methods=["POST"])
def cancel_task(task_id):
    """Cancel a queued or processing task"""
    status_info = task_statuses.get(task_id)
    if not status_info:
        return jsonify({"error": "Task ID not found"}), 404

    current_status = status_info.get("status")

    # Only allow cancelling queued or processing tasks
    if current_status not in ["queued", "processing"]:
        return jsonify({"error": f"Cannot cancel task with status: {current_status}"}), 400

    # Mark task as cancelled
    cancelled_tasks.add(task_id)

    # Update task status
    status_info.update({"status": "cancelled", "message": "Task cancelled by user", "completed_at": time.time()})
    task_statuses[task_id] = status_info
    COMPLETED_TASKS[task_id] = status_info

    app.logger.info(f"🚫 Task {task_id} cancelled by user")

    return jsonify({"success": True, "message": "Task cancelled"}), 200


@app.route("/download_processed/<task_id>", methods=["GET"])
def download_processed_file(task_id):
    status_info = task_statuses.get(task_id)
    if not status_info:
        app.logger.error(f"[DOWNLOAD_PROCESSED_ERROR] Task {task_id}: Task ID not found in status_info.")
        return jsonify({"error": "Task ID not found or task not processed"}), 404

    app.logger.info(f"[DOWNLOAD_PROCESSED] Task {task_id}: Status info: {status_info}")

    if status_info.get("status") == "completed":
        on_disk_base_filename = status_info.get("on_disk_filename")
        user_suggested_filename = status_info.get("filename")

        if not on_disk_base_filename:
            app.logger.error(
                f"[DOWNLOAD_PROCESSED_ERROR] Task {task_id}: 'on_disk_filename' not in "
                f"status_info for completed task. Status: {status_info}"
            )
            return (
                jsonify({"error": "File path (base) not recorded for completed task."}),
                500,
            )

        actual_file_path_on_disk = os.path.join(PROCESSED_FILES_DIR, on_disk_base_filename)

        if not user_suggested_filename:
            app.logger.warning(
                f"[DOWNLOAD_PROCESSED_WARNING] Task {task_id}: 'filename' (user-facing) not in status_info. "
                f"Using basename of actual path. Status: {status_info}"
            )
            user_suggested_filename = os.path.basename(actual_file_path_on_disk)

        app.logger.info(
            f"[DOWNLOAD_PROCESSED] Task {task_id}: Attempting to serve. "
            f"Disk path: '{actual_file_path_on_disk}', "
            f"User suggested name: '{user_suggested_filename}'"
        )

        if os.path.exists(actual_file_path_on_disk):
            # Sanitize the user-suggested filename for the download prompt
            download_name_header = sanitize_for_http_header(user_suggested_filename)
            app.logger.info(
                f"[DOWNLOAD_PROCESSED] Task {task_id}: File '{actual_file_path_on_disk}' found. "
                f"Serving as '{download_name_header}'."
            )
            return send_from_directory(
                os.path.dirname(actual_file_path_on_disk),
                os.path.basename(actual_file_path_on_disk),
                as_attachment=True,
                download_name=download_name_header,
            )
        else:
            app.logger.error(
                f"[DOWNLOAD_PROCESSED_ERROR] Task {task_id}: "
                f"File '{actual_file_path_on_disk}' (from 'filepath' key) not found on disk, "
                f"though task marked completed. Status: {status_info}"
            )
            return (
                jsonify({"error": "File not found on server (filepath invalid), though task marked completed."}),
                404,
            )

    elif status_info.get("status") == "failed":
        app.logger.info(f"[DOWNLOAD_PROCESSED] Task {task_id}: Task failed. Message: {status_info.get('message')}")
        return (
            jsonify({"error": f"Task failed: {status_info.get('message', 'Unknown error')}"}),
            500,
        )
    elif status_info.get("status") == "processing":
        app.logger.info(f"[DOWNLOAD_PROCESSED] Task {task_id}: Task still processing.")
        return jsonify({"error": "Task is still processing."}), 202
    elif status_info.get("status") == "queued":
        app.logger.info(f"[DOWNLOAD_PROCESSED] Task {task_id}: Task is queued.")
        return jsonify({"error": "Task is queued."}), 202
    else:
        app.logger.error(
            f"[DOWNLOAD_PROCESSED_ERROR] Task {task_id}: Unexpected task status or missing keys. Status: {status_info}"
        )
        return jsonify({"error": "Task not completed or file not available."}), 404


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(".", "favicon.ico")


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "Server is running"}), 200


# Start the background worker thread
# Ensure processed_files_dir exists when module loads
if not os.path.exists(PROCESSED_FILES_DIR):
    print(f"Creating processed files directory: {PROCESSED_FILES_DIR}", flush=True)
    os.makedirs(PROCESSED_FILES_DIR)

print("Initializing and starting background task worker...", flush=True)
worker_thread = threading.Thread(target=combination_worker_loop, daemon=True)
worker_thread.start()
print("Background task worker started.", flush=True)

# Record application start time for health checks
app.start_time = time.time()

# Start the cleanup scheduler
print("Starting automatic file cleanup scheduler...", flush=True)
schedule_cleanup()
print("File cleanup scheduler started.", flush=True)

if __name__ == "__main__":
    use_dev_server = os.environ.get("USE_DEV_SERVER", "true").lower() == "true"
    flask_port_info = int(os.environ.get("APP_PORT", 8080))

    if use_dev_server:
        print(
            f"🚀 Starting Flask development server on http://0.0.0.0:{flask_port_info}",
            flush=True,
        )
        # debug=True enables auto-reloader and debugger. Flask's reloader handles threads better.
        # threaded=True is generally good for dev server to handle multiple requests like polling.
        app.run(host="0.0.0.0", port=flask_port_info, debug=True, threaded=True)
    else:
        # When using Gunicorn, it will run the 'app' object directly.
        # The host and port will be configured via Gunicorn's command line arguments.
        print(
            "Application ready to be served by Gunicorn (or another WSGI server).",
            flush=True,
        )
        print(
            "To ensure the in-memory queue and worker thread function correctly with Gunicorn,",
            flush=True,
        )
        print(
            "it's recommended to run Gunicorn with a single worker process (--workers 1).",
            flush=True,
        )
        print(
            "Example: gunicorn --workers 1 --threads 4 --bind 0.0.0.0:8080 server:app",
            flush=True,
        )
