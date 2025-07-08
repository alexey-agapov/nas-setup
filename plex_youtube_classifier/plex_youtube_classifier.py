import argparse
import json
import os
import shutil
import subprocess
import hashlib
from pathlib import Path
import openai
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

BASE_PLEX_DIR = Path("/mnt/seagate/Plex Library")
WORKDIR = Path("/tmp/tmp_downloads")
LOG_FILE = Path("/var/log/yt-download-classifier.log")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

PLEX_LIBRARIES = {
    "Movies": BASE_PLEX_DIR / "Movies",
    "TV Shows": BASE_PLEX_DIR / "TV Shows",
    "YouTube et al": BASE_PLEX_DIR / "YouTube et al",
    "Music Videos": BASE_PLEX_DIR / "Music Videos",
    "Operas and Concerts": BASE_PLEX_DIR / "Operas and Concerts",
}

# ----------------- AGENT: DOWNLOAD -----------------
def download_video(url: str, download_dir: Path) -> Path:
    print("[+] Preparing deterministic filename...")
    download_dir.mkdir(parents=True, exist_ok=True)
    url_hash = hashlib.sha1(url.encode()).hexdigest()[:12]
    temp_filename = f"video_{url_hash}.mp4"
    output_path = download_dir / temp_filename

    if output_path.exists():
        print(f"[+] Video already exists at {output_path}, skipping download.")
        return output_path

    YT_DLP_CMD = "yt-dlp"
    cmd = [
        YT_DLP_CMD,
        "--no-simulate",
        "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "--merge-output-format", "mp4",
        "--embed-metadata",
        "--write-info-json",
        "-o", str(output_path),
        url
    ]

    subprocess.run(cmd, check=True)
    print(f"[+] Downloaded video: {output_path}")
    return output_path

# ----------------- AGENT: LOAD METADATA -----------------
def load_metadata(downloaded_video: Path) -> dict:
    json_file = downloaded_video.with_suffix(".info.json")
    if not json_file.exists():
        raise FileNotFoundError("Metadata JSON not found.")
    with open(json_file, "r", encoding="utf-8") as f:
        full_metadata = json.load(f)
    metadata = {
        "title": full_metadata.get("title"),
        "uploader": full_metadata.get("uploader"),
        "description": full_metadata.get("description"),
        "duration_string": full_metadata.get("duration_string"),
        "tags": full_metadata.get("tags", []),
        "upload_date": full_metadata.get("upload_date"),
    }
    print("[+] Loaded reduced metadata from JSON.")
    return metadata

# ----------------- AGENT: CLASSIFY -----------------
def classify_video(metadata: dict) -> dict:
    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").lower()

    system_prompt = (
        "You are a media librarian assistant. Classify videos into one of these categories: "
        "Movies, TV Shows, YouTube et al, Music Videos, Operas and Concerts. "
        "Based on title, uploader, description, duration, and tags, decide the best category. "
        "Then generate a filename in a format appropriate for the category using the title, uploader, release or upload date if relevant."
    )

    user_prompt = (
        f"Title: {metadata.get('title')}\n"
        f"Uploader: {metadata.get('uploader')}\n"
        f"Description: {metadata.get('description')}\n"
        f"Duration: {metadata.get('duration_string')}\n"
        f"Tags: {', '.join(metadata.get('tags', []))}\n\n"
        "Return valid JSON of the following structure: {\"category\": str, \"suggested_filename\": str}"
    )

    print(f"[+] Using LLM provider: {LLM_PROVIDER}")

    if LLM_PROVIDER == "openai":
        import openai
        OPENAI_MODEL = "gpt-4o"
        client = openai.OpenAI(api_key=OPENAI_API_KEY)

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
        )

        content = response.choices[0].message.content

    elif LLM_PROVIDER == "gemini":
        GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")

        response = model.generate_content(
            contents=f"{system_prompt}\n\n{user_prompt}",
            generation_config={
               "response_mime_type": "application/json"
            }
        )
        content = response.text

    else:
        raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")

    print(f"[+] LLM raw response: {content}")
    classification = json.loads(content)
    print(f"[+] Parsed classification: {classification}")
    return classification

# ----------------- AGENT: MOVE FILE -----------------
def move_video(downloaded_video: Path, classification: dict):
    category = classification['category']
    suggested_filename = classification['suggested_filename']

    if category not in PLEX_LIBRARIES:
        raise ValueError(f"Unknown category: {category}")

    target_dir = Path(PLEX_LIBRARIES[category])
    target_path = target_dir / suggested_filename
    target_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[+] Moving video to: {target_path}")
    shutil.move(str(downloaded_video), str(target_path))

# ----------------- MAIN -----------------
def main():
    parser = argparse.ArgumentParser(description="Download and classify YouTube video for Plex.")
    parser.add_argument("url", nargs="?", default="https://www.youtube.com/watch?v=nE-F-hrf09Q", help="Video URL to download")
    args = parser.parse_args()

    try:
        downloaded_video = download_video(args.url, WORKDIR)
        metadata = load_metadata(downloaded_video)
        classification = classify_video(metadata)
        move_video(downloaded_video, classification)
        print("[+] Done! Video downloaded, classified, and moved to Plex library.")
    except Exception as e:
        error_msg = f"[!] Error: {e}"
        print(error_msg)

if __name__ == "__main__":
    main()
