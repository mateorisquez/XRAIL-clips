import re
import asyncio
from youtube_transcript_api import YouTubeTranscriptApi

def extract_video_id(url: str) -> str:
    """Extract the YouTube video ID from various forms of URLs."""
    url = url.strip()
    # IDs are exactly 11 characters, preceded by `v=` or `/`, and followed by end of string, `?`, `&` or `/`
    match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})(?:\?|&|\/|$)', url)
    if match:
        return match.group(1)
            
    # If the user just passed exactly an 11-char ID directly
    if len(url) == 11 and not url.startswith("http"):
        return url
    
    return url # Return as-is if no match

def get_transcript_with_timestamps(video_id: str) -> list:
    """
    Fetch the transcript for a YouTube video with timestamps.
    Returns a list of dictionaries: [{'text': '...', 'start': 0.0, 'duration': 1.5}]
    """
    # Ensure an event loop exists for Streamlit's ScriptRunner thread
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    
    try:
        api = YouTubeTranscriptApi()
        # Try to get Spanish first, then fallback to English
        transcript_list = api.list(video_id)
        
        try:
            transcript = transcript_list.find_transcript(['es', 'es-419', 'en'])
        except Exception:
            # Fallback to the first available transcript
            transcript = transcript_list.find_transcript(['en'])
            
        return transcript.fetch()
    except Exception as e:
        error_msg = str(e)
        if "no element found" in error_msg.lower() or "is no longer available" in error_msg.lower():
            raise Exception("No se pudieron obtener los subtítulos. Es posible que el enlace sea incorrecto, que el video no tenga subtítulos, o que YouTube esté bloqueando la petición.")
        raise Exception(f"Error descargando la transcripción: {error_msg}")

def format_transcript_for_llm(transcript_data: list) -> str:
    """
    Formats the raw transcript data into a readable string with timestamps.
    Format: [MM:SS] Text
    """
    formatted_lines = []
    
    # We can consolidate very short lines to save tokens and improve readability
    current_text = ""
    current_start = 0
    current_duration = 0
    
    for entry in transcript_data:
        # In youtube-transcript-api v1.x, entry is a FetchedTranscriptSnippet object
        if hasattr(entry, 'start') and hasattr(entry, 'text'):
            start_seconds = getattr(entry, 'start')
            text = getattr(entry, 'text').replace('\n', ' ').strip()
        else: # Fallback dict
            start_seconds = entry['start']
            text = entry['text'].replace('\n', ' ').strip()
        
        minutes = int(start_seconds // 60)
        seconds = int(start_seconds % 60)
        timestamp = f"[{minutes:02d}:{seconds:02d}]"
        
        formatted_lines.append(f"{timestamp} {text}")
        
    return "\n".join(formatted_lines)
