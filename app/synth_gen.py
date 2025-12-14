import os
import shutil
from typing import Literal

from app.utils.strings import log_attempt_number
from app.utils.strings import make_cuid
from elevenlabs.client import ElevenLabs
import httpx
from loguru import logger
from pydantic import BaseModel

from app import tiktokvoice
from app.config import speech_cache_path
from app.utils.path_util import search_file, text_to_sha256_hash
from app.voice_presets import VOICE_PRESET, apply_voice_preset
from tenacity import retry, stop_after_attempt, wait_fixed

VOICE_PROVIDER = Literal["elevenlabs", "tiktok", "openai", "airforce"]


ELEVENLABS_MODEL = Literal["eleven_multilingual_v2", "eleven_v3"]


class SynthConfig(BaseModel):
    voice_provider: VOICE_PROVIDER = "tiktok"
    voice: str = "en_us_007"
    elevenlabs_model: ELEVENLABS_MODEL = "eleven_multilingual_v2"
    """ ElevenLabs model: eleven_multilingual_v2 (padrão estável), eleven_v3 (v3-alpha, melhor entonação) """

    voice_preset: VOICE_PRESET = "none"
    """ Preset de pós-processamento de voz: none, valorgi, podcast, radio, intimate, powerful """

    static_mode: bool = False
    """ if we're generating static audio for test """

    disable_cache: bool = False
    """ se True, ignora cache e força regeneração dos áudios """


class SynthGenerator:
    def __init__(self, cwd: str, config: SynthConfig):
        self.config = config
        self.cwd = cwd
        self.cache_key: str | None = None

        self.base = os.path.join(self.cwd, "audio_chunks")

        os.makedirs(self.base, exist_ok=True)

        self.client = ElevenLabs(
            api_key=os.getenv("ELEVENLABS_API_KEY"),
        )

    def set_speech_props(self):
        ky = (
            self.config.voice
            if self.config.static_mode
            else make_cuid(self.config.voice + "_")
        )
        self.speech_path = os.path.join(
            self.base,
            f"{self.config.voice_provider}_{ky}.mp3",
        )
        text_hash = text_to_sha256_hash(self.text)

        self.cache_key = f"{self.config.voice}_{text_hash}"

    async def generate_with_eleven(self, text: str) -> str:
        # ElevenLabs SDK 2.x - nova API
        model_id = self.config.elevenlabs_model
        logger.info(f"Using ElevenLabs model: {model_id}")
        logger.debug(f"Text to synthesize ({len(text)} chars): {text[:100]}...")

        # eleven_v3 NÃO suporta style e use_speaker_boost
        # eleven_multilingual_v2 suporta todos os parâmetros
        if model_id == "eleven_v3":
            voice_settings = {
                "stability": 0.5,  # v3 funciona melhor com valores mais neutros
                "similarity_boost": 0.75,
            }
        else:
            voice_settings = {
                "stability": 0.71,
                "similarity_boost": 0.5,
                "style": 0.0,
                "use_speaker_boost": True
            }

        try:
            audio = self.client.text_to_speech.convert(
                voice_id=self.config.voice,
                text=text,
                model_id=model_id,
                voice_settings=voice_settings
            )

            # Salvar o áudio (audio é um generator, precisamos iterar)
            with open(self.speech_path, "wb") as f:
                for chunk in audio:
                    f.write(chunk)

            return self.speech_path

        except Exception as e:
            error_msg = str(e)
            logger.error(f"ElevenLabs API error: {error_msg}")

            # Se v3 falhar, tentar com v2 como fallback
            if model_id == "eleven_v3":
                logger.warning(f"eleven_v3 failed ({error_msg}), falling back to eleven_multilingual_v2...")
                audio = self.client.text_to_speech.convert(
                    voice_id=self.config.voice,
                    text=text,
                    model_id="eleven_multilingual_v2",
                    voice_settings={
                        "stability": 0.71,
                        "similarity_boost": 0.5,
                        "style": 0.0,
                        "use_speaker_boost": True
                    }
                )
                with open(self.speech_path, "wb") as f:
                    for chunk in audio:
                        f.write(chunk)
                return self.speech_path

            raise

    async def generate_with_tiktok(self, text: str) -> str:
        tiktokvoice.tts(text, voice=str(self.config.voice), filename=self.speech_path)

        return self.speech_path

    async def cache_speech(self, text: str):
        try:
            if not self.cache_key:
                logger.warning("Skipping speech cache because it is not set")
                return

            speech_path = os.path.join(speech_cache_path, f"{self.cache_key}.mp3")
            shutil.copy2(self.speech_path, speech_path)
        except Exception as e:
            logger.exception(f"Error in cache_speech(): {e}")

    async def generate_with_openai(self, text: str) -> str:
        raise NotImplementedError

    async def generate_with_airforce(self, text: str) -> str:
        url = f"https://api.airforce/get-audio?text={text}&voice={self.config.voice}"
        async with httpx.AsyncClient() as client:
            res = await client.get(url)
            save(res.content, self.speech_path)
        return self.speech_path

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(4), after=log_attempt_number) # type: ignore
    async def synth_speech(self, text: str) -> str:
        self.text = text
        self.set_speech_props()

        # Só usa cache se disable_cache for False
        if not self.config.disable_cache:
            cached_speech = search_file(speech_cache_path, self.cache_key)

            if cached_speech:
                logger.info(f"Found speech in cache: {cached_speech}")
                shutil.copy2(cached_speech, self.speech_path)
                return cached_speech
        else:
            logger.info("Cache disabled - forcing regeneration")

        logger.info(f"Synthesizing text: {text}")

        genarator = None

        if self.config.voice_provider == "openai":
            genarator = self.generate_with_openai
        elif self.config.voice_provider == "airforce":
            genarator = self.generate_with_airforce
        elif self.config.voice_provider == "tiktok":
            genarator = self.generate_with_tiktok
        elif self.config.voice_provider == "elevenlabs":
            genarator = self.generate_with_eleven
        else:
            raise ValueError(
                f"voice provider {self.config.voice_provider} is not recognized"
            )

        speech_path = await genarator(text)

        # Aplicar preset de voz (pós-processamento FFmpeg)
        if self.config.voice_preset and self.config.voice_preset != "none":
            logger.info(f"Applying voice preset: {self.config.voice_preset}")
            speech_path = apply_voice_preset(speech_path, self.config.voice_preset)

        await self.cache_speech(text)

        return speech_path