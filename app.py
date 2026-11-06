#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename


ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
TEMPLATES = json.loads((ROOT / "templates.json").read_text())["templates"]
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".aiff", ".flac"}
JOBS: dict[str, dict] = {}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 250 * 1024 * 1024


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return value.strip("-") or "render"


def parse_progress(log_path: Path):
    if not log_path.exists():
        return None
    pattern = re.compile(r"^(\d+)/(\d+)$")
    for line in reversed(log_path.read_text(errors="ignore").splitlines()):
        match = pattern.match(line.strip())
        if match:
            return int(match.group(1)), int(match.group(2))
    return None


def job_payload(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return {"status": "error", "error": "Render job not found.", "progress": 0}
    status = job["status"]
    progress = 0.0
    eta = None
    message = "Preparing render..."
    parsed = parse_progress(job["log_path"])
    if parsed:
        current, total = parsed
        progress = min(0.98, current / total)
        elapsed = max(0.1, time.time() - job["started_at"])
        eta = elapsed * (total - current) / max(current, 1)
        message = f"Rendering frames {current}/{total}"
    if status == "done":
        progress, eta, message = 1.0, 0, "Render complete."
    payload = {
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "eta_seconds": eta,
        "message": message,
    }
    if status == "done":
        payload["video_url"] = f"/outputs/{job_id}/{job['output'].name}"
    if status == "error":
        payload["error"] = job.get("error", "Render failed.")
    return payload


def run_job(job_id: str):
    job = JOBS[job_id]
    try:
        with job["log_path"].open("w") as log:
            result = subprocess.run(job["command"], stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            job["status"] = "error"
            job["error"] = f"Renderer exited with code {result.returncode}."
        else:
            job["status"] = "done"
    except Exception as exc:
        job["status"] = "error"
        job["error"] = str(exc)


@app.get("/")
def index():
    return render_template("index.html", templates=TEMPLATES)


@app.post("/api/render")
def start_render():
    upload = request.files.get("audio")
    if not upload or not upload.filename:
        return jsonify(error="Choose an audio file first."), 400
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return jsonify(error="Unsupported audio format."), 400

    template_id = request.form.get("template_id", "pulse_body")
    template = next((item for item in TEMPLATES if item["id"] == template_id), None)
    if not template:
        return jsonify(error="Unknown template."), 400

    job_id = uuid.uuid4().hex[:12]
    job_dir = OUTPUTS / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    audio_path = job_dir / secure_filename(f"input{suffix}")
    upload.save(audio_path)

    track = request.form.get("track_title", "Untitled Track").strip() or "Untitled Track"
    output = job_dir / f"{slugify(track)}-{template_id}.mp4"
    command = [
        sys.executable,
        str(ROOT / template["renderer"]),
        "--audio", str(audio_path),
        "--output", str(output),
        "--source", str(ROOT / template["source"]),
        "--track-title", track,
        "--album-title", request.form.get("album_title", "Sound Field Study"),
        "--label-name", request.form.get("label_name", "REVE LABS SOUND"),
        "--archive-code", request.form.get("archive_code", "RLS-PBH-001 / SOUND FIELD STUDY"),
        "--crf", request.form.get("crf", "23"),
        "--stream",
    ]
    duration = request.form.get("max_duration", "").strip()
    if duration:
        try:
            if float(duration) <= 0:
                raise ValueError
        except ValueError:
            return jsonify(error="Preview duration must be a positive number."), 400
        command.extend(["--max-duration", duration])

    JOBS[job_id] = {
        "status": "running",
        "started_at": time.time(),
        "command": command,
        "output": output,
        "log_path": job_dir / "render.log",
    }
    threading.Thread(target=run_job, args=(job_id,), daemon=True).start()
    return jsonify(job_id=job_id, status="running")


@app.get("/api/jobs/<job_id>")
def get_job(job_id: str):
    payload = job_payload(job_id)
    return jsonify(payload), 404 if payload["status"] == "error" and "not found" in payload.get("error", "").lower() else 200


@app.get("/outputs/<job_id>/<path:filename>")
def output_file(job_id: str, filename: str):
    return send_from_directory(OUTPUTS / job_id, filename, as_attachment=False)


@app.get("/assets/<path:filename>")
def asset_file(filename: str):
    return send_from_directory(ROOT / "assets", filename, as_attachment=False)


if __name__ == "__main__":
    OUTPUTS.mkdir(exist_ok=True)
    app.run(host="127.0.0.1", port=8787, debug=False)
