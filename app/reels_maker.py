import asyncio
import math
import os

import ffmpeg
from loguru import logger

from app.base import (
    BaseEngine,
    BaseGeneratorConfig,
    FileClip,
    StartResponse,
    TempData,
)
from app.utils.strings import split_by_dot_or_newline, sanitize_sentences_for_subtitles
from app.utils.path_util import download_resource


class ReelsMakerConfig(BaseGeneratorConfig):
    pass


def create_concat_file(clips):
    concat_filename = "concat_list.txt"
    with open(concat_filename, "w") as f:
        for clip in clips:
            f.write(f"file '{clip}'\n")
    return concat_filename


def concatenate_with_filelist(clips, output_path):
    concat_filename = create_concat_file(clips)

    # Run FFmpeg with the concat demuxer
    ffmpeg.input(concat_filename, format="concat", safe=0).output(
        output_path, c="copy"
    ).run(overwrite_output=True)

    return output_path


def concatenate_clips(clips, output_path):
    """
    Concatenates a list of video clips.
    Args:
    - clips (list of str): List of file paths to each video clip to concatenate.
    - output_path (str): Path to save the final concatenated video.
    """
    # Prepare input streams for each clip
    streams = [ffmpeg.input(clip) for clip in clips]

    # Use concat filter
    concatenated_stream = ffmpeg.concat(*streams, v=1, a=1).output(output_path)

    # Run FFmpeg
    concatenated_stream.run(overwrite_output=True)
    return output_path


class ReelsMaker(BaseEngine):
    def __init__(self, config: ReelsMakerConfig):
        super().__init__(config)

        self.config = config

        logger.info(f"Starting Reels Maker with: {self.config.model_dump()}")

    async def generate_script(self, sentence: str, duration_seconds: int = 60):
        # Determinar qual modelo TTS será usado para otimizar o prompt
        tts_model = "default"
        if self.config.synth_config.voice_provider == "elevenlabs":
            tts_model = self.config.synth_config.elevenlabs_model  # "eleven_v3" ou "eleven_multilingual_v2"

        logger.debug(f"Generating script from prompt: {sentence} (target: {duration_seconds}s, tts_model={tts_model})")
        sentence = await self.prompt_generator.generate_sentence(
            sentence,
            duration_seconds=duration_seconds,
            tts_model=tts_model
        )
        return sentence.replace('"', "")

    async def generate_search_terms(self, script, max_hashtags: int = 5):
        """Legacy method - generates generic search terms from entire script"""
        logger.debug("Generating search terms for script...")
        response = await self.prompt_generator.generate_stock_image_keywords(script)
        tags = [tag.replace("#", "") for tag in response.sentences]
        if len(tags) > max_hashtags:
            logger.warning(f"Truncated search terms to {max_hashtags} tags")
            tags = tags[:max_hashtags]

        logger.info(f"Generated search terms: {tags}")
        return tags

    async def generate_sequential_search_terms(self, sentences: list[str]) -> list[str]:
        """
        Generates one English search keyword per sentence for better video matching.

        This method produces keywords that are:
        - In English (for best API results)
        - Concrete and visual (what you'd actually see)
        - Sequential (each keyword matches its corresponding sentence)

        Args:
            sentences: List of script sentences

        Returns:
            List of English keywords, one per sentence
        """
        logger.debug(f"Generating sequential search terms for {len(sentences)} sentences...")
        keywords = await self.prompt_generator.generate_sequential_video_keywords(sentences)
        logger.info(f"Generated sequential keywords: {keywords}")
        return keywords

    async def start(self, progress_callback=None) -> StartResponse:
        """
        Inicia a geração do vídeo.

        Args:
            progress_callback: Função opcional para reportar progresso (recebe string)
        """
        await super().start()

        def report(msg: str):
            """Helper para reportar progresso"""
            logger.info(msg)
            if progress_callback:
                try:
                    progress_callback(msg)
                except:
                    pass  # Ignora erros no callback

        # Inicializar background_music_path como None para evitar AttributeError
        self.background_music_path = None

        if self.config.background_audio_url:
            report("Baixando música de fundo...")
            self.background_music_path = await download_resource(
                self.cwd, self.config.background_audio_url
            )

        # ============================================================
        # FASE 1: Gerar script com duração alvo
        # ============================================================
        report("📝 Fase 1/5: Gerando roteiro com IA...")
        if self.config.prompt:
            script = await self.generate_script(
                self.config.prompt,
                duration_seconds=self.config.script_duration
            )
        elif self.config.script:
            script = self.config.script
        else:
            raise ValueError("No prompt or sentence provided")

        assert script is not None, "Script should not be None"

        sentences = split_by_dot_or_newline(script, 100)
        sentences = list(filter(lambda x: x != "", sentences))

        report(f"✓ Roteiro: {len(sentences)} sentenças, ~{len(script.split())} palavras")

        # ============================================================
        # FASE 2: Gerar áudios TTS PRIMEIRO (para saber duração exata)
        # ============================================================
        report("🎤 Fase 2/5: Sintetizando narração (TTS)...")
        data: list[TempData] = []

        for i, sentence in enumerate(sentences):
            report(f"   Áudio {i+1}/{len(sentences)}...")
            audio_path = await self.synth_generator.synth_speech(sentence)
            data.append(
                TempData(
                    synth_clip=FileClip(audio_path),
                )
            )

        # Calcular duração total do vídeo baseado nos áudios gerados
        video_duration = sum(item.synth_clip.real_duration for item in data)
        report(f"✓ Narração: {video_duration:.1f} segundos de áudio")

        # ============================================================
        # FASE 3: Calcular quantos vídeos únicos precisamos
        # ============================================================
        max_clip_duration = 3  # cada take dura no máximo 3 segundos

        # Quantidade exata de takes necessários (sem repetição)
        videos_needed = math.ceil(video_duration / max_clip_duration)

        # ============================================================
        # FASE 4: Buscar/baixar vídeos (com keywords sequenciais em inglês)
        # ============================================================
        report(f"🎬 Fase 3/5: Buscando {videos_needed} vídeos no Pexels...")
        video_paths = []
        if self.config.video_paths:
            report("Usando vídeos enviados pelo usuário...")
            video_paths = self.config.video_paths
        else:
            # Gerar keywords sequenciais (um por sentença, em inglês, visuais)
            search_terms = await self.generate_sequential_search_terms(sentences)
            report(f"   Keywords (EN): {', '.join(search_terms[:5])}{'...' if len(search_terms) > 5 else ''}")

            # Buscar vídeos únicos suficientes
            video_paths = await self.video_generator.get_unique_videos(
                search_terms=search_terms,
                count_needed=videos_needed
            )

        if len(video_paths) == 0:
            raise ValueError("No video paths found available")

        report(f"✓ Baixados: {len(video_paths)} vídeos únicos")

        # ============================================================
        # FASE 5: Montar os clipes finais
        # ============================================================
        report("🎞️ Fase 4/5: Gerando legendas...")
        # Só sobrescrever se tiver baixado música de URL, preservar upload
        if self.background_music_path:
            self.video_generator.config.background_music_path = self.background_music_path

        final_speech = ffmpeg.concat(
            *[item.synth_clip.ffmpeg_clip for item in data], v=0, a=1
        )

        # get subtitles from script (usando texto limpo, sem caracteres de entonação)
        clean_sentences = sanitize_sentences_for_subtitles(sentences)
        subtitles_path = await self.subtitle_generator.generate_subtitles(
            sentences=clean_sentences,
            durations=[item.synth_clip.real_duration for item in data],
        )

        tot_dur: float = 0
        final_clips: list[FileClip] = []
        video_index = 0

        # Duração mínima para um clipe (evita erros de FFmpeg com clipes muito curtos)
        min_clip_duration = 0.5

        while tot_dur < video_duration:
            # Pegar próximo vídeo (ciclando se necessário, mas com mais vídeos não deve precisar)
            video_path = video_paths[video_index % len(video_paths)]
            video_index += 1

            remaining_dur = video_duration - tot_dur

            # Se o tempo restante for muito curto, ignorar (o vídeo ficará ligeiramente mais curto)
            if remaining_dur < min_clip_duration:
                logger.debug(f"Skipping final clip ({remaining_dur:.2f}s < {min_clip_duration}s min)")
                break

            subclip_duration = min(max_clip_duration, remaining_dur)

            subclip = FileClip(video_path, t=subclip_duration).duplicate()
            final_clips.append(subclip)
            tot_dur += subclip_duration

            logger.debug(
                f"Clip {video_index}: +{subclip_duration:.1f}s = {tot_dur:.1f}s / {video_duration:.1f}s"
            )

        report(f"✓ Legendas geradas")
        report(f"🔧 Fase 5/5: Renderizando vídeo final ({len(final_clips)} clipes)...")

        final_video_path = await self.video_generator.generate_video(
            clips=final_clips,
            subtitles_path=subtitles_path,
            speech_filter=final_speech,
            video_duration=video_duration,
        )

        report(f"✅ Vídeo finalizado: {video_duration:.0f}s")

        return StartResponse(
            video_file_path=final_video_path,
        )