import asyncio
import multiprocessing
import os
import typing
from uuid import uuid4

from loguru import logger
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile
from app.reels_maker import ReelsMaker, ReelsMakerConfig
from app.synth_gen import VOICE_PROVIDER, ELEVENLABS_MODEL, SynthConfig
from app.video_gen import VideoGeneratorConfig, SUBTITLE_PRESETS, get_subtitle_preset_names
from app.color_presets import PRESETS, get_preset_names
from app.voice_presets import VOICE_PRESETS, VOICE_PRESET
from app.tiktokvoice import VOICES as TIKTOK_VOICES
from elevenlabs.client import ElevenLabs


if "queue" not in st.session_state:
    st.session_state["queue"] = {}


@st.cache_data(ttl=3600)  # Cache por 1 hora
def get_elevenlabs_voices():
    """Carrega vozes do ElevenLabs dinamicamente"""
    try:
        client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        voices = client.voices.get_all()
        voice_dict = {}
        for voice in voices.voices:
            labels = voice.labels or {}
            lang = labels.get("language", "?")
            accent = labels.get("accent", "")
            # Formato: "Nome (idioma) - categoria"
            display_name = f"{voice.name} ({lang}"
            if accent:
                display_name += f"/{accent}"
            display_name += f") - {voice.category}"
            voice_dict[display_name] = voice.voice_id
        return voice_dict
    except Exception as e:
        logger.error(f"Erro ao carregar vozes ElevenLabs: {e}")
        return {"Default Voice": "pNInz6obpgDQGcFmaJgB"}

queue: dict[str, ReelsMakerConfig] = st.session_state["queue"]


async def download_to_path(dest: str, buff: UploadedFile) -> str:
    with open(dest, "wb") as f:
        f.write(buff.getbuffer())
    return dest


async def main():
    st.title("AI Reels Story Maker")
    st.write("Create Engaging Faceless Videos for Social Media in Seconds")
    st.write(
        "Our tools make it easy to create captivating faceless videos that boost engagement and reach on social media in seconds."
    )
    st.divider()

    sentence_tab, prompt_tab = st.tabs(
        ["Enter your motivational quote", "Enter Prompt"]
    )

    with sentence_tab:
        sentence = st.text_area(
            label="Enter your quote",
            placeholder="Nothing is impossible. The word itself says 'I'm possible!, Champions keep playing until they get it right, You are never too old to set another goal or to dream a new dream.",
            height=100,
        )

    with prompt_tab:
        prompt = st.text_area(
            label="Enter your prompt",
            placeholder="A motivation quote about life & pleasure",
            height=100,
        )

    # Slider de duração do vídeo
    st.divider()
    script_duration = st.slider(
        "Target video duration (seconds)",
        min_value=30,
        max_value=180,
        value=60,
        step=15,
        help="Longer videos = more words in script = more unique video clips needed"
    )

    st.write("Choose background videos")
    auto_video_tab, upload_video_tab = st.tabs(["Auto Add video", "Upload Videos"])

    with auto_video_tab:
        st.write(
            "We'll automatically download background videos related to your prompt, usefull when you don't have a background video"
        )

    with upload_video_tab:
        uploaded_videos = st.file_uploader(
            "Upload a background videos",
            type=["mp4", "webm"],
            accept_multiple_files=True,
        )

    st.write("Choose a background audio")
    upload_audio_tab, audio_url_tab = st.tabs(["Upload audio", "Enter Audio Url"])

    with upload_audio_tab:
        uploaded_audio = st.file_uploader(
            "Upload a background audio", type=["mp3", "webm"]
        )

    with audio_url_tab:
        st.warning("Sorry, this feature is not available yet")
        background_audio_url = st.text_input(
            "Enter a background audio URL", placeholder="Enter URL"
        )

    # Seleção de provider primeiro para mostrar vozes corretas
    voice_provider = st.selectbox("Select voice provider", ["elevenlabs", "tiktok"])

    # Vozes baseadas no provider selecionado
    if voice_provider == "elevenlabs":
        elevenlabs_voices = get_elevenlabs_voices()
        # Ordenar: português primeiro, depois o resto
        sorted_voices = sorted(elevenlabs_voices.keys(), key=lambda x: (
            0 if "(pt" in x.lower() else 1,  # PT primeiro
            0 if "cloned" in x.lower() or "generated" in x.lower() else 1,  # Custom depois
            x.lower()
        ))
        voice_display = st.selectbox("Choose a voice", sorted_voices)
        voice = elevenlabs_voices[voice_display]  # Pega o voice_id

        # Seletor de modelo ElevenLabs
        elevenlabs_model = st.selectbox(
            "ElevenLabs Model",
            options=["eleven_multilingual_v2", "eleven_v3"],
            index=0,
            help="multilingual_v2: estável | eleven_v3: v3-alpha com melhor entonação"
        )
    else:
        # TikTok voices
        voice = st.selectbox("Choose a voice", TIKTOK_VOICES)
        elevenlabs_model = "eleven_multilingual_v2"  # Default quando não usa ElevenLabs

    # Voice Preset (pós-processamento de áudio)
    st.divider()
    st.subheader("🎙️ Voice Preset (Pós-processamento)")

    voice_preset_options = list(VOICE_PRESETS.keys())
    voice_preset = st.selectbox(
        "Preset de Voz",
        options=voice_preset_options,
        index=0,  # "none" por padrão
        format_func=lambda x: f"{VOICE_PRESETS[x].name} - {VOICE_PRESETS[x].description}",
        help="Aplica pós-processamento FFmpeg para modificar o timbre e dinâmica da voz"
    )

    # Mostrar detalhes do preset selecionado
    if voice_preset != "none":
        with st.expander("ℹ️ Detalhes do preset"):
            preset_info = VOICE_PRESETS[voice_preset]
            st.markdown(f"**{preset_info.name}**")
            st.markdown(preset_info.description)
            st.code(preset_info.ffmpeg_filters, language="bash")

    # Color grading preset
    st.divider()
    st.subheader("Color Grading")

    preset_options = get_preset_names()
    preset_descriptions = {name: PRESETS[name].description for name in preset_options}

    color_preset = st.selectbox(
        "Color Preset",
        options=preset_options,
        index=0,  # "none" por padrão
        format_func=lambda x: f"{x.title()} - {preset_descriptions[x]}"
    )

    st.divider()
    st.subheader("Subtitles")

    # Seletor de preset de legenda
    subtitle_preset_options = get_subtitle_preset_names()
    subtitle_preset = st.selectbox(
        "Subtitle Template",
        options=subtitle_preset_options,
        index=0,  # "custom" por padrão
        format_func=lambda x: f"{SUBTITLE_PRESETS[x]['name']} - {SUBTITLE_PRESETS[x]['description']}"
    )

    # Pegar valores do preset selecionado
    selected_preset = SUBTITLE_PRESETS[subtitle_preset]
    is_custom = subtitle_preset == "custom"

    col1, col2, col3 = st.columns(3)

    # Video Gen config - valores do preset ou custom
    with col1:
        text_color = st.color_picker(
            "Subtitles Text color",
            value=selected_preset["text_color"],
            disabled=not is_custom
        )

    with col2:
        stroke_color = st.color_picker(
            "Subtitles Stroke color",
            value=selected_preset["stroke_color"],
            disabled=not is_custom
        )

    with col3:
        bg_color = st.color_picker(
            "Subtitles Background color (None)",
            value=None,
        )

    col4, col5, col6 = st.columns(3)
    with col4:
        stroke_width = st.number_input(
            "Stroke width",
            value=selected_preset["stroke_width"],
            step=1,
            min_value=1,
            disabled=not is_custom
        )

    with col5:
        fontsize = st.number_input(
            "Font size",
            value=selected_preset["fontsize"],
            step=1,
            min_value=1,
            disabled=not is_custom
        )

    with col6:
        subtitles_position = st.selectbox("Subtitles position", ["center,center"])

    # Se não for custom, usa valores do preset (override do disabled)
    if not is_custom:
        text_color = selected_preset["text_color"]
        stroke_color = selected_preset["stroke_color"]
        stroke_width = selected_preset["stroke_width"]
        fontsize = selected_preset["fontsize"]

    # text_color = st.color_picker("Text color", value="#ffffff")
    cpu_count = multiprocessing.cpu_count()
    if cpu_count > 1:
        cpu_count = cpu_count - 1

    threads = st.number_input("Threads", value=cpu_count, step=1, min_value=1)

    # Opção para forçar regeneração
    force_regenerate = st.checkbox(
        "🔄 Forçar regeneração (ignorar cache)",
        value=False,
        help="Marca esta opção para gerar novos áudios mesmo que já existam no cache"
    )

    submitted = st.button("Generate Reels", use_container_width=True, type="primary")

    if submitted:
        queue_id = str(uuid4())

        cwd = os.path.join(os.getcwd(), "tmp", queue_id)
        os.makedirs(cwd, exist_ok=True)

        # create config
        config = ReelsMakerConfig(
            job_id="".join(str(uuid4()).split("-")),
            background_audio_url=background_audio_url,
            prompt=prompt,
            script_duration=script_duration,  # Duração alvo do vídeo
            video_gen_config=VideoGeneratorConfig(
                bg_color=str(bg_color),
                fontsize=int(fontsize),
                stroke_color=str(stroke_color),
                stroke_width=int(stroke_width),
                subtitles_position=str(subtitles_position),
                text_color=str(text_color),
                threads=int(threads),
                color_preset=str(color_preset),  # Preset de color grading
                subtitle_preset=str(subtitle_preset),  # Preset de legenda
                # watermark_path="images/watermark.png",
            ),
            synth_config=SynthConfig(
                voice=str(voice),
                voice_provider=typing.cast(VOICE_PROVIDER, voice_provider or "tiktok"),
                elevenlabs_model=typing.cast(ELEVENLABS_MODEL, elevenlabs_model),
                voice_preset=typing.cast(VOICE_PRESET, voice_preset),
                disable_cache=force_regenerate,
            ),
        )

        # read all uploaded files and save in a path
        if uploaded_videos:
            config.video_paths = [
                await download_to_path(dest=os.path.join(config.cwd, p.name), buff=p)
                for p in uploaded_videos
            ]

        # read uploaded file and save in a path
        if uploaded_audio:
            config.video_gen_config.background_music_path = await download_to_path(
                dest=os.path.join(config.cwd, "background.mp3"), buff=uploaded_audio
            )

        print(f"starting reels maker: {config.model_dump_json()}")

        # Status com logs em tempo real
        with st.status("🎬 Gerando vídeo...", expanded=True) as status:
            try:
                if len(queue.items()) > 1:
                    raise Exception("queue is full - someone else is generating reels")

                queue[queue_id] = config

                reels_maker = ReelsMaker(config)

                # Info sobre modelo v3
                if config.synth_config.elevenlabs_model == "eleven_v3":
                    st.caption("_🎭 Usando ElevenLabs v3 com tags de entonação_")

                # Info sobre voice preset
                if config.synth_config.voice_preset and config.synth_config.voice_preset != "none":
                    preset_name = VOICE_PRESETS[config.synth_config.voice_preset].name
                    st.caption(f"_🎙️ Voice preset: {preset_name}_")

                # Callback que escreve no st.status
                output = await reels_maker.start(
                    progress_callback=lambda msg: st.write(msg)
                )

                status.update(label="✅ Vídeo gerado com sucesso!", state="complete", expanded=False)
                st.balloons()
                st.video(output.video_file_path, autoplay=True)

                # Ler o arquivo como bytes para o download funcionar
                with open(output.video_file_path, "rb") as video_file:
                    st.download_button(
                        "⬇️ Download Reels",
                        data=video_file.read(),
                        file_name="reels.mp4",
                        mime="video/mp4"
                    )

            except Exception as e:
                if queue_id in queue:
                    del queue[queue_id]
                logger.exception(f"removed from queue: {queue_id}: -> {e}")
                status.update(label="❌ Erro na geração", state="error")
                st.error(e)


if __name__ == "__main__":
    asyncio.run(main())
