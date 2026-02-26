import re
import asyncio
import requests
from xml.etree import ElementTree
from html import unescape

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    HAS_YT_API = True
except ImportError:
    HAS_YT_API = False


def extract_video_id(url: str) -> str:
    """Extract the YouTube video ID from various forms of URLs."""
    url = url.strip()
    # Handle full URLs: youtube.com/watch?v=ID, youtu.be/ID, youtube.com/embed/ID, etc.
    match = re.search(r'(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})(?:\?|&|\/|$)', url)
    if match:
        return match.group(1)
            
    # If the user just passed exactly an 11-char ID directly
    if len(url) == 11 and not url.startswith("http"):
        return url
    
    return url  # Return as-is if no match


def get_transcript_with_timestamps(video_id: str) -> list:
    """
    Fetch the transcript for a YouTube video with timestamps.
    Tries youtube-transcript-api first, falls back to InnerTube API if blocked.
    """
    # Ensure an event loop exists for Streamlit's ScriptRunner thread
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    
    # Method 1: Try youtube-transcript-api
    if HAS_YT_API:
        try:
            api = YouTubeTranscriptApi()
            transcript_list = api.list(video_id)
            try:
                transcript = transcript_list.find_transcript(['es', 'es-419', 'en'])
            except Exception:
                transcript = transcript_list.find_transcript(['en'])
            return transcript.fetch()
        except Exception as e:
            error_msg = str(e)
            # If it's an IP block, try the fallback
            if "blocked" in error_msg.lower() or "ip" in error_msg.lower() or "cloud" in error_msg.lower():
                pass  # Fall through to Method 2
            elif "no element found" in error_msg.lower():
                pass  # Fall through to Method 2
            else:
                raise Exception(f"Error descargando la transcripción: {error_msg}")

    # Method 2: Fallback — InnerTube API (direct HTTP, works from some cloud IPs)
    return _fetch_transcript_innertube(video_id)


def _fetch_transcript_innertube(video_id: str) -> list:
    """
    Fetch transcript using YouTube's InnerTube API directly.
    Tries multiple client identities to maximize compatibility.
    """
    clients = [
        {
            "context": {"client": {"clientName": "ANDROID", "clientVersion": "19.09.36", "androidSdkVersion": 34, "hl": "es", "gl": "ES"}},
            "ua": "com.google.android.youtube/19.09.36 (Linux; U; Android 14) gzip"
        },
        {
            "context": {"client": {"clientName": "WEB", "clientVersion": "2.20240101.00.00", "hl": "es", "gl": "ES"}},
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        },
    ]

    tracks = None
    for client in clients:
        try:
            resp = requests.post(
                "https://www.youtube.com/youtubei/v1/player",
                json={"videoId": video_id, "context": client["context"]},
                headers={"Content-Type": "application/json", "User-Agent": client["ua"]},
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            found = data.get("captions", {}).get("playerCaptionsTracklistRenderer", {}).get("captionTracks", [])
            if found:
                tracks = found
                break
        except Exception:
            continue

    if not tracks:
        raise Exception(
            "No se pudieron obtener subtítulos del video. "
            "YouTube está bloqueando las peticiones desde esta IP de servidor. "
            "Prueba corriendo la app localmente con: streamlit run app.py"
        )

    # Pick language: es > es-419 > en > first available
    track_url = None
    for lang in ["es", "es-419", "en"]:
        for t in tracks:
            if t.get("languageCode") == lang:
                track_url = t.get("baseUrl")
                break
        if track_url:
            break
    if not track_url:
        track_url = tracks[0].get("baseUrl")

    # Fetch caption XML
    caption_resp = requests.get(track_url, timeout=15)
    caption_resp.raise_for_status()

    # Parse XML into list of dicts (same format as youtube-transcript-api)
    root = ElementTree.fromstring(caption_resp.text)
    result = []
    for elem in root:
        if elem.text:
            start = float(elem.attrib.get("start", "0"))
            duration = float(elem.attrib.get("dur", "0"))
            text = unescape(elem.text).replace("\n", " ").strip()
            result.append({"text": text, "start": start, "duration": duration})

    if not result:
        raise Exception("La transcripción está vacía.")

    return result


def format_transcript_for_llm(transcript_data: list) -> str:
    """
    Formats the raw transcript data into a readable string with timestamps.
    Format: [MM:SS] Text
    """
    formatted_lines = []
    
    for entry in transcript_data:
        # Support both FetchedTranscriptSnippet objects and dicts
        if hasattr(entry, 'start') and hasattr(entry, 'text'):
            start_seconds = getattr(entry, 'start')
            text = getattr(entry, 'text').replace('\n', ' ').strip()
        else:
            start_seconds = entry['start']
            text = entry['text'].replace('\n', ' ').strip()
        
        minutes = int(start_seconds // 60)
        seconds = int(start_seconds % 60)
        timestamp = f"[{minutes:02d}:{seconds:02d}]"
        
        formatted_lines.append(f"{timestamp} {text}")
        
    return "\n".join(formatted_lines)
