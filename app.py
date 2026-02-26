import streamlit as st
import os
from dotenv import load_dotenv

from extractor import extract_video_id, get_transcript_with_timestamps, format_transcript_for_llm
from analyzer import analyze_transcript

# Load environment variables
load_dotenv()

st.set_page_config(
    page_title="XRail Podcast Clipper",
    page_icon="🎙️",
    layout="centered"
)

st.title("🎙️ XRail Podcast - Generador de Clips")
st.markdown("Pega el enlace de tu episodio de YouTube y deja que la IA busque los mejores momentos para Shorts/Reels.")

# Sidebar for API Key
with st.sidebar:
    st.header("Configuración")
    api_key_input = st.text_input("Gemini API Key", type="password", value=os.environ.get("GEMINI_API_KEY", ""))
    if api_key_input:
        os.environ["GEMINI_API_KEY"] = api_key_input
    
    st.markdown("---")
    st.markdown("### Instrucciones")
    st.markdown("1. Ingresa la URL de YouTube")
    st.markdown("2. Asegúrate de tener configurada tu API Key de Gemini (puedes ponerla en el archivo `.env`)")
    st.markdown("3. Selecciona 'Generar Clips'")

url_input = st.text_input("URL de YouTube", placeholder="https://www.youtube.com/watch?v=...")

if st.button("🎬 Generar Clips", type="primary"):
    if not url_input:
        st.warning("Por favor, ingresa una URL válida de YouTube.")
    elif not os.environ.get("GEMINI_API_KEY"):
        st.error("Por favor, configura tu API Key de Gemini en la barra lateral.")
    else:
        with st.spinner("Analizando el video... esto puede tomar unos segundos."):
            try:
                # 1. Extract Video ID
                video_id = extract_video_id(url_input)
                st.info(f"✅ Video ID detectado: `{video_id}` (longitud: {len(video_id)})")
                
                # 2. Extract Transcript
                with st.status("Descargando transcripción...", expanded=True) as status:
                    raw_transcript = get_transcript_with_timestamps(video_id)
                    formatted_transcript = format_transcript_for_llm(raw_transcript)
                    status.update(label=f"✅ Transcripción descargada ({len(formatted_transcript.splitlines())} líneas encontradas)", state="complete")
                    
                # 3. Request Clips from Gemini
                with st.status("Buscando los mejores momentos con IA...", expanded=False) as status:
                    # To avoid passing huge transcripts that exceed context limits, 
                    # we could split it, but Gemini 1.5/2.5 Flash has a massive 1M+ token window.
                    # We pass the entire transcript directly.
                    ai_response = analyze_transcript(formatted_transcript)
                    clips = ai_response.get("clips", [])
                    status.update(label="Análisis completado", state="complete")
                
                # 4. Display Clips
                st.success("¡Clips generados con éxito!")
                
                for i, clip in enumerate(clips):
                    with st.expander(f"📌 Clip #{i+1} : {clip.get('start_time')} - {clip.get('end_time')}", expanded=True):
                        st.markdown(f"**Gancho (Primeros 3 segs):** {clip.get('hook')}")
                        st.markdown(f"**Copy para Reels/Shorts:**\n\n```text\n{clip.get('copy')}\n```")
                        st.markdown(f"**¿Por qué este clip?** {clip.get('reasoning')}")
                        
                        # Add a convenient link to jump directly to the timestamp
                        # Calculate seconds from MM:SS for the youtube link
                        try:
                            time_parts = clip.get('start_time').split(':')
                            seconds = int(time_parts[0]) * 60 + int(time_parts[1])
                            st.markdown(f"[▶️ Ver este momento en YouTube](https://youtu.be/{video_id}?t={seconds})")
                        except Exception:
                            pass
                            
            except Exception as e:
                st.error(f"Ocurrió un error: {str(e)}")
