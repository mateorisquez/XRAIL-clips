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
    st.markdown("2. Asegúrate de tener configurada tu API Key de Gemini")
    st.markdown("3. Selecciona cuántos clips quieres")
    st.markdown("4. Click en **Generar Clips**")

url_input = st.text_input("URL de YouTube", placeholder="https://www.youtube.com/watch?v=... o pega el ID del video")

col1, col2 = st.columns([3, 1])
with col1:
    clip_count = st.slider("¿Cuántos clips quieres generar?", min_value=1, max_value=10, value=6)
with col2:
    st.write("")  # spacer

# Manual transcript option (for cloud deployments where YouTube blocks IPs)
with st.expander("📋 ¿Error de IP bloqueada? Pega la transcripción aquí", expanded=False):
    st.markdown("""
    Si YouTube bloquea la descarga automática (común en servidores cloud), puedes pegar la transcripción manualmente:
    
    **Cómo obtener la transcripción de YouTube:**
    1. Abre el video en YouTube
    2. Haz click en **⋯** (los tres puntos debajo del video)
    3. Selecciona **"Mostrar transcripción"**
    4. Copia todo el texto y pégalo aquí abajo
    """)
    manual_transcript = st.text_area(
        "Transcripción (pegar aquí)",
        height=200,
        placeholder="[00:00] Bienvenidos al podcast...\n[00:05] Hoy vamos a hablar de..."
    )

if st.button("🎬 Generar Clips", type="primary", use_container_width=True):
    if not url_input and not manual_transcript:
        st.warning("Por favor, ingresa una URL válida de YouTube o pega una transcripción.")
    elif not os.environ.get("GEMINI_API_KEY"):
        st.error("Por favor, configura tu API Key de Gemini en la barra lateral.")
    else:
        with st.spinner("Analizando el video... esto puede tomar unos segundos."):
            try:
                video_id = extract_video_id(url_input) if url_input else ""
                
                # Determine transcript source
                if manual_transcript and manual_transcript.strip():
                    # Use manually pasted transcript
                    formatted_transcript = manual_transcript.strip()
                    st.info(f"📋 Usando transcripción pegada ({len(formatted_transcript.splitlines())} líneas)")
                else:
                    # Auto-fetch transcript
                    if not video_id:
                        st.warning("Ingresa una URL de YouTube o pega la transcripción manualmente.")
                        st.stop()
                    
                    st.info(f"✅ Video ID detectado: `{video_id}`")
                    
                    with st.status("Descargando transcripción...", expanded=True) as status:
                        raw_transcript = get_transcript_with_timestamps(video_id)
                        formatted_transcript = format_transcript_for_llm(raw_transcript)
                        status.update(label=f"✅ Transcripción descargada ({len(formatted_transcript.splitlines())} líneas)", state="complete")
                    
                # Analyze with Gemini
                with st.status("Buscando los mejores momentos con IA...", expanded=False) as status:
                    ai_response = analyze_transcript(formatted_transcript, clip_count=clip_count)
                    clips = ai_response.get("clips", [])
                    status.update(label="Análisis completado", state="complete")
                
                # Display Clips
                st.success(f"¡{len(clips)} clips generados con éxito!")
                
                for i, clip in enumerate(clips):
                    with st.expander(f"📌 Clip #{i+1} : {clip.get('start_time')} - {clip.get('end_time')}", expanded=True):
                        st.markdown(f"**Gancho (Primeros 3 segs):** {clip.get('hook')}")
                        st.markdown(f"**Copy para Reels/Shorts:**\n\n```text\n{clip.get('copy')}\n```")
                        st.markdown(f"**¿Por qué este clip?** {clip.get('reasoning')}")
                        
                        if video_id:
                            try:
                                time_parts = clip.get('start_time').split(':')
                                seconds = int(time_parts[0]) * 60 + int(time_parts[1])
                                st.markdown(f"[▶️ Ver este momento en YouTube](https://youtu.be/{video_id}?t={seconds})")
                            except Exception:
                                pass
                            
            except Exception as e:
                st.error(f"Ocurrió un error: {str(e)}")
