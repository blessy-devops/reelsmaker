"""
Voice Presets - Pós-processamento de áudio com FFmpeg

Presets de áudio inspirados em estilos de criadores de conteúdo.
Cada preset aplica uma cadeia de filtros FFmpeg para transformar o timbre e dinâmica da voz.
"""

import os
import subprocess
import shutil
from typing import Literal, Optional
from pydantic import BaseModel
from loguru import logger


# Tipos de presets disponíveis
VOICE_PRESET = Literal["none", "valorgi", "podcast", "radio", "intimate", "powerful"]


class VoicePreset(BaseModel):
    """Configuração de um preset de voz"""
    name: str
    description: str
    ffmpeg_filters: str


# Definição dos presets
VOICE_PRESETS: dict[str, VoicePreset] = {
    "none": VoicePreset(
        name="Nenhum",
        description="Sem pós-processamento - áudio original do TTS",
        ffmpeg_filters=""
    ),

    "valorgi": VoicePreset(
        name="Valorgi",
        description="Voz potente e próxima, com graves reforçados e compressão pesada. Estilo motivacional/vendas.",
        ffmpeg_filters=(
            "acompressor=threshold=-24dB:ratio=8:attack=5:release=50:makeup=6,"
            "lowshelf=f=200:g=4,"
            "equalizer=f=3000:t=q:w=1:g=2,"
            "alimiter=limit=0.95:attack=5:release=50,"
            "loudnorm=I=-14:TP=-1:LRA=4"
        )
    ),

    "podcast": VoicePreset(
        name="Podcast",
        description="Voz clara e balanceada, ideal para conteúdo longo. Compressão moderada.",
        ffmpeg_filters=(
            "acompressor=threshold=-20dB:ratio=4:attack=10:release=100:makeup=3,"
            "equalizer=f=120:t=q:w=1:g=2,"
            "equalizer=f=2500:t=q:w=1:g=1.5,"
            "highpass=f=80,"
            "loudnorm=I=-16:TP=-1:LRA=7"
        )
    ),

    "radio": VoicePreset(
        name="Rádio/Locutor",
        description="Voz de locutor profissional, com presença forte e graves encorpados.",
        ffmpeg_filters=(
            "acompressor=threshold=-18dB:ratio=6:attack=5:release=80:makeup=5,"
            "lowshelf=f=250:g=3,"
            "equalizer=f=3500:t=q:w=1:g=3,"
            "equalizer=f=8000:t=q:w=1:g=1,"
            "alimiter=limit=0.95:attack=5:release=50,"
            "loudnorm=I=-14:TP=-1:LRA=5"
        )
    ),

    "intimate": VoicePreset(
        name="Íntimo",
        description="Voz suave e próxima, como se falasse ao pé do ouvido. Ideal para ASMR/storytelling.",
        ffmpeg_filters=(
            "acompressor=threshold=-30dB:ratio=10:attack=3:release=30:makeup=8,"
            "lowshelf=f=150:g=5,"
            "highshelf=f=8000:g=-3,"
            "alimiter=limit=0.90:attack=3:release=30,"
            "loudnorm=I=-16:TP=-2:LRA=3"
        )
    ),

    "powerful": VoicePreset(
        name="Poderoso",
        description="Voz extremamente impactante, máxima compressão. Para conteúdo de alta energia.",
        ffmpeg_filters=(
            "acompressor=threshold=-28dB:ratio=12:attack=3:release=40:makeup=8,"
            "lowshelf=f=180:g=5,"
            "equalizer=f=2000:t=q:w=1:g=2,"
            "equalizer=f=4000:t=q:w=1:g=3,"
            "alimiter=limit=0.98:attack=3:release=30,"
            "loudnorm=I=-12:TP=-0.5:LRA=2"
        )
    ),
}


def get_preset_choices() -> dict[str, str]:
    """Retorna dict de nome_display -> preset_key para uso em UI"""
    return {preset.name: key for key, preset in VOICE_PRESETS.items()}


def get_preset_descriptions() -> dict[str, str]:
    """Retorna dict de preset_key -> description para tooltips"""
    return {key: preset.description for key, preset in VOICE_PRESETS.items()}


class VoicePresetProcessor:
    """Processador de presets de voz usando FFmpeg"""

    def __init__(self, ffmpeg_path: Optional[str] = None):
        """
        Args:
            ffmpeg_path: Caminho para o executável do FFmpeg.
                        Se None, tenta encontrar automaticamente.
        """
        self.ffmpeg_path = ffmpeg_path or self._find_ffmpeg()

    def _find_ffmpeg(self) -> str:
        """Encontra o FFmpeg no sistema"""
        # Tenta caminhos comuns
        common_paths = [
            "/opt/homebrew/bin/ffmpeg",  # macOS Apple Silicon
            "/usr/local/bin/ffmpeg",     # macOS Intel / Linux
            "/usr/bin/ffmpeg",           # Linux
            "ffmpeg"                      # PATH do sistema
        ]

        for path in common_paths:
            if shutil.which(path):
                return path

        # Fallback para o comando genérico
        return "ffmpeg"

    def apply_preset(
        self,
        input_path: str,
        preset_key: VOICE_PRESET,
        output_path: Optional[str] = None
    ) -> str:
        """
        Aplica um preset de voz a um arquivo de áudio.

        Args:
            input_path: Caminho do áudio de entrada
            preset_key: Chave do preset a aplicar ("none", "valorgi", etc)
            output_path: Caminho de saída. Se None, sobrescreve o original.

        Returns:
            Caminho do arquivo processado
        """
        # Se preset é "none", não faz nada
        if preset_key == "none":
            logger.info("Voice preset: none - skipping post-processing")
            return input_path

        preset = VOICE_PRESETS.get(preset_key)
        if not preset:
            logger.warning(f"Unknown voice preset: {preset_key}, skipping")
            return input_path

        if not preset.ffmpeg_filters:
            logger.info(f"Voice preset '{preset_key}' has no filters, skipping")
            return input_path

        # Define output path
        if output_path is None:
            # Cria arquivo temporário e depois substitui o original
            base, ext = os.path.splitext(input_path)
            temp_output = f"{base}_processed{ext}"
            replace_original = True
        else:
            temp_output = output_path
            replace_original = False

        logger.info(f"Applying voice preset: {preset.name}")
        logger.debug(f"FFmpeg filters: {preset.ffmpeg_filters}")

        # Monta comando FFmpeg
        cmd = [
            self.ffmpeg_path,
            "-y",                    # Sobrescreve sem perguntar
            "-i", input_path,        # Input
            "-af", preset.ffmpeg_filters,  # Filtros de áudio
            "-c:a", "libmp3lame",    # Codec MP3
            "-q:a", "2",             # Qualidade alta
            temp_output
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 60 segundos de timeout
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                raise RuntimeError(f"FFmpeg failed: {result.stderr}")

            logger.info(f"Voice preset applied successfully: {temp_output}")

            # Se deve substituir o original
            if replace_original:
                os.replace(temp_output, input_path)
                logger.debug(f"Replaced original file: {input_path}")
                return input_path
            else:
                return temp_output

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timed out")
            raise RuntimeError("FFmpeg processing timed out")
        except Exception as e:
            logger.exception(f"Error applying voice preset: {e}")
            raise


# Instância global para uso fácil
_processor: Optional[VoicePresetProcessor] = None


def get_processor() -> VoicePresetProcessor:
    """Retorna instância singleton do processador"""
    global _processor
    if _processor is None:
        _processor = VoicePresetProcessor()
    return _processor


def apply_voice_preset(input_path: str, preset_key: VOICE_PRESET) -> str:
    """
    Função de conveniência para aplicar preset.

    Args:
        input_path: Caminho do áudio
        preset_key: Preset a aplicar

    Returns:
        Caminho do arquivo processado
    """
    return get_processor().apply_preset(input_path, preset_key)
