import os
import tempfile
import subprocess
import hashlib
import hmac
import base64
import time
import json
import requests
from flask import Flask, request, render_template, redirect, url_for
from pydub import AudioSegment

app = Flask(__name__)

# ACRCloud credentials
ACR_HOST = "identify-ap-southeast-1.acrcloud.com"
ACCESS_KEY = "71f558e238472520b2f8fd90abe2162f"
ACCESS_SECRET = "Si1IVCyItLh21UK6qI8IScw5MHkiHMFvk7lSWAnT"


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    if request.method == "POST":
        video_url = request.form["video_url"]
        try:
            # Step 1: Download and extract audio
            with tempfile.TemporaryDirectory() as tmpdir:
                audio_path = os.path.join(tmpdir, "audio.wav")
                subprocess.run([
                    "yt-dlp",
                    "--cookies", "fb_cookies.txt",
                    "--no-check-certificate",
                    "-x", "--audio-format", "wav",
                    "--postprocessor-args", "-ss 0 -t 30",
                    "-o", os.path.join(tmpdir, "audio.%(ext)s"),
                    video_url
                ], check=True)

                # Step 2: Load and trim audio
                audio_file = [f for f in os.listdir(tmpdir) if f.endswith(".wav")][0]
                full_audio = AudioSegment.from_wav(os.path.join(tmpdir, audio_file))
                sample_audio = full_audio[:15000]  # First 15 seconds
                sample_path = os.path.join(tmpdir, "sample.wav")
                sample_audio.export(sample_path, format="wav")

                # Step 3: Identify with ACRCloud
                result = identify_audio(sample_path)

                # Extract title and create YouTube search link
                music_data = result.get("metadata", {}).get("music")
                if music_data and isinstance(music_data, list) and len(music_data) > 0:
                    title = music_data[0].get("title")
                    if title:
                        result[
                            "youtube_search"] = f"https://www.youtube.com/results?search_query={title.replace(' ', '+')} Song"
        except Exception as e:
            result = {"status": {"msg": str(e), "code": 1}}

    return render_template("index.html", result=result)


def identify_audio(file_path):
    http_method = "POST"
    http_uri = "/v1/identify"
    data_type = "audio"
    signature_version = "1"
    timestamp = str(int(time.time()))

    string_to_sign = f"{http_method}\n{http_uri}\n{ACCESS_KEY}\n{data_type}\n{signature_version}\n{timestamp}"
    sign = base64.b64encode(
        hmac.new(ACCESS_SECRET.encode('utf-8'), string_to_sign.encode('utf-8'), digestmod=hashlib.sha1).digest()
    ).decode('utf-8')

    with open(file_path, 'rb') as f:
        sample_bytes = f.read()

    files = {
        'sample': ('sample.wav', sample_bytes, 'audio/wav')
    }

    data = {
        'access_key': ACCESS_KEY,
        'sample_bytes': str(len(sample_bytes)),
        'timestamp': timestamp,
        'signature': sign,
        'data_type': data_type,
        'signature_version': signature_version
    }

    response = requests.post(f"https://{ACR_HOST}/v1/identify", files=files, data=data)
    return response.json()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
