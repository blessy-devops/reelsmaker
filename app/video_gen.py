import multiprocessing
import os
import random
from typing import TYPE_CHECKING, Literal
from pathlib import Path

from app.effects import zoom_in_effect, zoom_out_effect
from app.color_presets import apply_color_preset, get_preset, get_preset_names
from app.utils.strings import (
    FFMPEG_TYPE,
    FileClip,
    adjust_audio_to_target_dBFS,
    get_video_size,
    web_color_to_ass,
)
from loguru import logger
from app.pexel import search_for_stock_videos
from PIL import Image
from PIL import Image as pil
from pkg_resources import parse_version
from pydantic import BaseModel
import ffmpeg


if parse_version(pil.__version__) >= parse_version("10.0.0"):
    Image.ANTIALIAS = Image.LANCZOS  # type: ignore

if TYPE_CHECKING:
    from app.base import BaseEngine

# TODO: implement me
positions = {
    "center": ["center", "center"],
    "left": ["left", "center"],
    "right": ["right", "center"],
    "top": ["center", "top"],
    "bottom": ["center", "bottom"],
}


# ============================================================
# SUBTITLE PRESETS
# ============================================================

SUBTITLE_PRESETS = {
    "custom": {
        "name": "Custom",
        "description": "Configuração manual",
        "fontsize": 35,
        "stroke_width": 1,
        "text_color": "#ffffff",
        "stroke_color": "#000000",
    },
    "valorgi": {
        "name": "Valorgi",
        "description": "Clean e minimalista",
        "fontsize": 40,
        "stroke_width": 1,
        "text_color": "#ffffff",
        "stroke_color": "#000000",
    },
    "bold": {
        "name": "Bold",
        "description": "Texto grande e destacado",
        "fontsize": 60,
        "stroke_width": 3,
        "text_color": "#ffffff",
        "stroke_color": "#000000",
    },
    "classic": {
        "name": "Classic",
        "description": "Estilo clássico com stroke grosso",
        "fontsize": 50,
        "stroke_width": 4,
        "text_color": "#ffffff",
        "stroke_color": "#000000",
    },
}


def get_subtitle_preset_names() -> list[str]:
    """Retorna lista de nomes de presets de legenda disponíveis."""
    return list(SUBTITLE_PRESETS.keys())


class VideoGeneratorConfig(BaseModel):
    fontsize: int = 35  # NOVO DEFAULT (era 70)
    stroke_color: str = "#000000"  # Preto (era branco)
    text_color: str = "#ffffff"
    stroke_width: int | None = 1  # NOVO DEFAULT (era 5)
    font_name: str = "Cinzel"
    bg_color: str | None = None
    subtitles_position: str = "center,center"
    subtitle_preset: str = "custom"
    """ subtitle preset (custom, valorgi, bold, classic) """
    threads: int = multiprocessing.cpu_count()

    watermark_path_or_text: str | None = None
    watermark_opacity: float = 0.5
    watermark_type: Literal["image", "text", "none"] = "none"
    background_music_path: str | None = None

    aspect_ratio: str = "9:16"
    """ aspect ratio of the video """

    color_effect: str = "gray"
    color_preset: str = "none"
    """ color grading preset (none, valorgi, warm_vintage, cold_cinematic, etc) """


class VideoGenerator:
    def __init__(
        self,
        base_class: "BaseEngine",
    ):
        self.job_id = base_class.config.job_id
        self.config = base_class.config.video_gen_config
        self.cwd = base_class.cwd
        self.base_engine = base_class

        self.ffmpeg_cmd = os.path.join(os.getcwd(), "bin/ffmpeg")

    async def get_video_url(self, search_term: str) -> str | None:
        try:
            urls = await search_for_stock_videos(
                limit=2,
                min_dur=10,
                query=search_term,
            )
            return urls[0] if len(urls) > 0 else None
        except Exception as e:
            logger.error(f"Consistency Violation: {e}")

        return None

    async def get_unique_videos(
        self,
        search_terms: list[str],
        count_needed: int
    ) -> list[str]:
        """
        Busca e baixa a quantidade exata de vídeos únicos necessários.
        Não repete vídeos - cada URL é única.
        """
        from app.utils.path_util import download_resource
        import asyncio

        unique_urls: set[str] = set()
        videos_per_term = max(5, (count_needed // len(search_terms)) + 2)

        logger.info(f"Searching for {count_needed} unique videos across {len(search_terms)} terms")

        # Buscar vídeos de cada termo
        for search_term in search_terms:
            if len(unique_urls) >= count_needed:
                break

            try:
                urls = await search_for_stock_videos(
                    limit=videos_per_term,
                    min_dur=5,  # Reduzido de 10 para 5 segundos (só precisamos de 3s por take)
                    query=search_term,
                )
                for url in urls:
                    if url not in unique_urls:
                        unique_urls.add(url)
                        if len(unique_urls) >= count_needed:
                            break

                logger.debug(f"Term '{search_term}': found {len(urls)} videos, total unique: {len(unique_urls)}")

            except Exception as e:
                logger.warning(f"Error searching '{search_term}': {e}")
                continue

        if len(unique_urls) < count_needed:
            logger.warning(
                f"Only found {len(unique_urls)} unique videos, needed {count_needed}. "
                "Videos may repeat."
            )

        # Baixar todos os vídeos em paralelo
        logger.info(f"Downloading {len(unique_urls)} unique videos...")
        tasks = [
            asyncio.create_task(download_resource(self.cwd, url))
            for url in unique_urls
        ]
        local_paths = await asyncio.gather(*tasks, return_exceptions=True)

        # Filtrar erros
        valid_paths = [
            path for path in local_paths
            if isinstance(path, str) and path
        ]

        logger.info(f"Successfully downloaded {len(valid_paths)} videos")
        return valid_paths

    def apply_subtitle(self, clip, subtitle_path: str):
        position = self.config.subtitles_position.split(",")[0]
        styles = {
            "bottom": "Alignment=2",
            "center": "Alignment=10",
            "top": "Alignment=6",
        }

        text_color = web_color_to_ass(self.config.text_color)
        stroke_color = web_color_to_ass(self.config.stroke_color)
        font_size = round(self.config.fontsize / 5)

        style = (
            f"FontName={self.config.font_name},FontSize={font_size},"
            f"PrimaryColour={text_color},OutlineColour={stroke_color},Outline={self.config.stroke_width},Bold=1,"
            f"{styles.get(position, 'Alignment=10')}"
        )

        fonts_dir = "./narrator/sys/fonts"
        return clip.filter(
            "subtitles", filename=subtitle_path, fontsdir=fonts_dir, force_style=style
        )

    def add_audio_mix(self, video_stream, background_music_filter, tts_audio_filter):
        audio_mix = ffmpeg.filter(
            stream_spec=[background_music_filter, tts_audio_filter],
            filter_name="amix",
            duration="longest",
            dropout_transition=0,
        )
        return ffmpeg.concat(video_stream, audio_mix, v=1, a=1)

    def concatenate_clips(self, inputs: list[FileClip], effects: list = []):
        processed_clips = []

        # Carregar preset de cor uma vez
        color_preset = get_preset(self.config.color_preset)
        logger.info(f"Using color preset: {color_preset.name}")

        for data in inputs:
            clip = data.ffmpeg_clip

            if len(effects) > 0:
                effect = random.choice(effects)
                clip = effect(clip)

            # ============================================================
            # NORMALIZAÇÃO: fps, resolução, SAR e formato
            # ============================================================
            clip = clip.filter("fps", fps=30)  # Normalizar para 30fps

            # Scale inteligente que funciona para QUALQUER orientação:
            # 1. Escala para que o MENOR lado preencha o frame (1080x1920)
            # 2. Isso garante que sempre haverá pixels suficientes para o crop
            clip = clip.filter(
                "scale",
                w=1080,
                h=1920,
                force_original_aspect_ratio="increase"
            )

            # Crop centralizado para 1080x1920 (corta o excesso)
            clip = clip.filter("crop", 1080, 1920)

            # IMPORTANTE: Normalizar SAR (Sample Aspect Ratio) para 1:1
            # Alguns vídeos têm SAR diferente (ex: 10240:10239) que quebra o concat
            clip = clip.filter("setsar", "1")

            clip = clip.filter("format", "yuv420p")  # Formato de pixel compatível

            # ============================================================
            # COLOR GRADING: aplicar preset ANTES das legendas
            # ============================================================
            clip = apply_color_preset(clip, color_preset)

            # apply gray effect for motivational video (legacy)
            if (
                self.config.color_effect == "gray"
                and self.base_engine.config.video_type == "motivational"
            ):
                clip = clip.filter("format", "gray")

            processed_clips.append(clip)

        final_video = ffmpeg.concat(*processed_clips, v=1, a=0)
        return final_video

    async def generate_video(
        self,
        clips: list[FileClip],  # the list of clips from ffmpeg
        speech_filter: FFMPEG_TYPE,
        subtitles_path: str,
        video_duration: float,
    ) -> str:
        logger.info("Generating video...")

        # TEMPORARIAMENTE DESABILITADO: zoompan causa erro com vídeos de fps diferentes
        # effects = [zoom_out_effect, zoom_in_effect]
        effects = []  # Sem efeitos de zoom por enquanto

        # Define output path
        output_path = (Path(self.cwd) / f"{self.job_id}_final.mp4").as_posix()

        if self.base_engine.config.video_type == "motivational":
            effects = []

        video_stream = self.concatenate_clips(clips, effects)
        video_stream = self.apply_watermark(video_stream)
        video_stream = self.apply_subtitle(video_stream, subtitles_path)

        # Música de fundo é opcional - só adiciona mix se tiver música
        if self.config.background_music_path:
            music_input = ffmpeg.input(
                adjust_audio_to_target_dBFS(self.config.background_music_path),
                t=video_duration,
            )
            video_stream = self.add_audio_mix(
                video_stream=video_stream,
                tts_audio_filter=speech_filter,
                background_music_filter=music_input,
            )
        else:
            # Sem música de fundo - só usa a narração
            video_stream = ffmpeg.concat(video_stream, speech_filter, v=1, a=1)

        output = ffmpeg.output(
            video_stream,
            output_path,
            vcodec="libx264",
            acodec="aac",
            preset="veryfast",
            threads=2,
            # loglevel="quiet",
        )

        ffmpeg_args = output.get_args()
        logger.info(f"FFMPEG CMD: {self.ffmpeg_cmd} {' '.join(ffmpeg_args)}")
        try:
            stdout, stderr = output.run(
                overwrite_output=True,
                cmd=self.ffmpeg_cmd,
                capture_stdout=True,
                capture_stderr=True
            )
            logger.info("Video generation complete.")
            if stderr:
                logger.debug(f"FFmpeg stderr: {stderr.decode('utf-8', errors='ignore')[-2000:]}")
        except ffmpeg.Error as e:
            stderr_text = e.stderr.decode('utf-8', errors='ignore') if e.stderr else 'No stderr'
            logger.error(f"FFmpeg FULL error:\n{stderr_text}")
            logger.error(f"FFmpeg command was: {self.ffmpeg_cmd} {' '.join(ffmpeg_args)}")
            # Salvar erro em arquivo para debug
            error_log_path = "/tmp/ffmpeg_error.log"
            with open(error_log_path, "w") as f:
                f.write(f"=== FFmpeg Error Log ===\n")
                f.write(f"Command: {self.ffmpeg_cmd} {' '.join(ffmpeg_args)}\n\n")
                f.write(f"Stderr:\n{stderr_text}\n")
            logger.error(f"Error saved to: {error_log_path}")
            raise
        return output_path

    # def get_background_audio(self, video_clip: VideoClip, song_path: str) -> AudioClip:
    #     """Takes the original audio and adds the background audio"""
    #     logger.info(f"Getting background music: {song_path}")

    #     def adjust_audio_to_target_dBFS(audio_file_path: str, target_dBFS=-30.0):
    #         audio = AudioSegment.from_file(audio_file_path)
    #         change_in_dBFS = target_dBFS - audio.dBFS
    #         adjusted_audio = audio.apply_gain(change_in_dBFS)
    #         adjusted_audio.export(audio_file_path, format="mp3")
    #         logger.info(f"Adjusted audio to target dBFS: {target_dBFS}")
    #         return audio_file_path

    #     # set the volume of the song to 10% of the original volume
    #     song_path = adjust_audio_to_target_dBFS(song_path)

    #     background_audio = AudioFileClip(song_path)

    #     if background_audio.duration < video_clip.duration:
    #         # calculate how many times the background audio needs to repeat
    #         repeats_needed = int(video_clip.duration // background_audio.duration) + 1

    #         # create a list of the background audio repeated
    #         background_audio_repeated = concatenate_audioclips(
    #             [background_audio] * repeats_needed
    #         )

    #         # trim the repeated audio to match the video duration
    #         background_audio_repeated = background_audio_repeated.subclip(
    #             0, video_clip.duration
    #         )
    #     else:
    #         background_audio_repeated = background_audio.subclip(0, video_clip.duration)

    #     comp_audio = CompositeAudioClip([video_clip.audio, background_audio_repeated])

    #     return comp_audio

    def crop(self, clip: FileClip) -> FFMPEG_TYPE:
        width, height = get_video_size(clip.filepath)
        aspect_ratio = width / height
        ffmpeg_clip = clip.ffmpeg_clip

        if aspect_ratio < 0.5625:
            crop_height = int(width / 0.5625)
            return ffmpeg_clip.filter(
                "crop", w=width, h=crop_height, x=0, y=(height - crop_height) // 2
            )
        else:
            crop_width = int(0.5625 * height)
            return ffmpeg_clip.filter(
                "crop", w=crop_width, h=height, x=(width - crop_width) // 2, y=0
            )

    def apply_watermark(self, video_stream):
        """Adds a watermark to the bottom-right of the video."""

        sysfont = os.path.join(os.getcwd(), "narrator/sys/fonts/luckiestguy.ttf")

        # Check if watermark path/text is set and watermark type is valid
        if (
            not self.config.watermark_path_or_text
            or self.config.watermark_type == "none"
        ):
            return video_stream  # No watermark, return original stream

        # Text-based watermark
        if self.config.watermark_type == "text":
            watermark_text = self.config.watermark_path_or_text
            video_stream = video_stream.filter(
                "drawtext",
                text=watermark_text,
                x="if(lt(mod(t,20),10), (main_w-text_w)-16, if(lt(mod(t,20),10), 16, if(lt(mod(t,20),15), 16, (main_w-text_w)-16)))",
                y="if(lt(mod(t,20),10), (main_h-text_h)-100, if(lt(mod(t,20),10), 50, if(lt(mod(t,20),15), (main_h-text_h)-100, 50)))",
                fontsize=40,
                fontcolor="white",
                fontfile=sysfont,
            )
            logger.warning(f"Using text watermark with font: {sysfont}")

        # Image-based watermark
        elif self.config.watermark_type == "image":
            watermark_path = self.config.watermark_path_or_text
            watermark = ffmpeg.input(watermark_path)

            # Resize watermark to a height of 100 while maintaining aspect ratio
            watermark = watermark.filter("scale", -1, 100)

            # Overlay the watermark in the bottom-right corner with 8px padding
            video_stream = ffmpeg.overlay(
                video_stream,
                watermark,
                x="(main_w-overlay_w)-8",
                y="(main_h-overlay_h)-8",
            )

        logger.debug("Added watermark to video.")
        return video_stream

    async def create_gif(
        self, master_video_path: str, start_time: float = 1.0, end_time: float = 1.5
    ) -> str:
        logger.debug("Creating GIF...")
        gif_path = f"{self.cwd}/{self.job_id}.gif"

        (
            ffmpeg.input(master_video_path, ss=start_time, t=end_time - start_time)
            .filter("fps", fps=6)
            .filter("scale", "iw/2", "ih/2")
            .output(gif_path, format="gif", loop=0, pix_fmt="rgb24")
            .run(overwrite_output=True)
        )

        return gif_path