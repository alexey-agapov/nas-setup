from yt_dlp.extractor import gen_extractors
from yt_dlp import YoutubeDL
import hashlib

class YouTubeDLAgent:
    def __init__(self, download_dir: str):
        self.download_dir = download_dir

    def can_handle(self, url: str) -> bool:
        for extractor in gen_extractors():
            if extractor.suitable(url) and extractor.IE_NAME != 'generic':
                return True
        return False
    
    def download(self, url: str, hook=None):
        self.download_dir.mkdir(parents=True, exist_ok=True)
        url_hash = hashlib.sha1(url.encode()).hexdigest()[:12]
        temp_filename = f"video_{url_hash}.mp4"
        output_path = self.download_dir / temp_filename

        if output_path.exists():
            return output_path
        
        ydl_opts = {
            "simulate": False,
            "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "merge_output_format": "mp4",
            "embed_metadata": True,
            "writeinfojson": True,
            "outtmpl": str(output_path),
        }
        if hook:
            ydl_opts["progress_hooks"] = [hook]
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        return output_path
