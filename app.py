from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import subprocess
import tempfile
import os
import uuid

app = Flask(__name__)
CORS(app)

app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB


@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "message": "TikTok Encoder server is running"
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/encode", methods=["POST"])
def encode():

    if "video" not in request.files:
        return jsonify({
            "error": "No video uploaded"
        }), 400

    video = request.files["video"]

    if not video.filename:
        return jsonify({
            "error": "No video selected"
        }), 400

    crf = request.form.get("crf", "18")
    fps = request.form.get("fps", "original")
    resolution = request.form.get("resolution", "original")

    # Validate CRF
    try:
        crf_number = int(crf)
        if crf_number < 16 or crf_number > 28:
            crf_number = 18
    except:
        crf_number = 18

    # Validate FPS
    if fps not in ["original", "30", "60"]:
        fps = "original"

    # Validate resolution
    if resolution not in ["original", "720", "1080"]:
        resolution = "original"

    job_id = str(uuid.uuid4())

    input_path = os.path.join(
        tempfile.gettempdir(),
        job_id + "_input"
    )

    output_path = os.path.join(
        tempfile.gettempdir(),
        job_id + "_optimized.mp4"
    )

    try:

        video.save(input_path)

        command = [
            "ffmpeg",
            "-y",
            "-i", input_path,

            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", str(crf_number),

            "-pix_fmt", "yuv420p",

            "-c:a", "aac",
            "-b:a", "192k",

            "-movflags", "+faststart"
        ]

        if fps != "original":
            command += [
                "-r", fps
            ]

        if resolution != "original":
            command += [
                "-vf",
                f"scale=-2:{resolution}"
            ]

        command.append(output_path)

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=900
        )

        if result.returncode != 0:
            error_text = result.stderr.decode(
                "utf-8",
                errors="ignore"
            )

            return jsonify({
                "error": "FFmpeg encoding failed",
                "details": error_text[-2000:]
            }), 500

        return send_file(
            output_path,
            mimetype="video/mp4",
            as_attachment=True,
            download_name="tiktok-optimized.mp4"
        )

    except subprocess.TimeoutExpired:

        return jsonify({
            "error": "Encoding timed out"
        }), 504

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500

    finally:

        # Clean up input immediately.
        if os.path.exists(input_path):
            try:
                os.remove(input_path)
            except:
                pass


if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 10000)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
