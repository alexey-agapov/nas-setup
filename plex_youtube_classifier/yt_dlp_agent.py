from yt_dlp.extractor import gen_extractors

class YouTubeDLAgent:
    def can_handle(self, url: str) -> bool:
        for extractor in gen_extractors():
            if extractor.suitable(url) and extractor.IE_NAME != 'generic':
                return True
        return False
