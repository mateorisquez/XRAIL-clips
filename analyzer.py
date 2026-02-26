import os
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

class ClipSuggestion(BaseModel):
    start_time: str = Field(description="The exact start time of the clip from the transcript (e.g., '15:20')")
    end_time: str = Field(description="The exact end time of the clip from the transcript (e.g., '16:15')")
    hook: str = Field(description="The catchy opening line or 'hook' for the first 3 seconds of the clip")
    copy: str = Field(description="The social media copy, including engaging text and relevant hashtags")
    reasoning: str = Field(description="Why this specific clip is highly engaging and likely to perform well")

class ClipSuggestionsResponse(BaseModel):
    clips: list[ClipSuggestion]

def analyze_transcript(transcript_text: str, clip_count: int = 6) -> dict:
    """
    Analyzes the transcript using Gemini to find raw clip suggestions.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError("Please provide a valid GEMINI_API_KEY in the .env file")

    clip_count = min(max(int(clip_count), 1), 10)
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    Eres un experto productor de podcasts, administrador de redes sociales y creador de contenido viral.
    Tu trabajo es analizar la siguiente transcripción de un podcast (que incluye marcas de tiempo) y seleccionar 
    los {clip_count} MEJORES momentos para convertirlos en clips cortos (Shorts/Reels/TikToks).
    
    Reglas estrictas:
    1. CADA CLIP DEBE DURAR MENOS DE 60 SEGUNDOS. Mide cuidadosamente las marcas de tiempo.
    2. El clip debe tener sentido por sí solo (sin el contexto completo del episodio).
    3. Busca momentos de debate intenso, opiniones fuertes, consejos útiles o historias divertidas.
    4. Proporciona un "Gancho" (Hook) fuerte para los primeros 3 segundos. El gancho DEBE SER TEXTO LITERAL de la transcripción, palabras textuales que se digan en ese momento del clip, NO un resumen ni una reescritura.
    5. Escribe un copy atractivo para la publicación en redes sociales, incluyendo hashtags (ej. para un podcast de startups/tech/etc).
    
    Aquí está la transcripción del podcast:
    {transcript_text}
    """

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ClipSuggestionsResponse,
            temperature=0.7,
        ),
    )
    
    return json.loads(response.text)
