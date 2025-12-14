#!/usr/bin/env python3
"""
Script de teste manual para debugar a geração de vídeo.
Usa as mesmas configurações que o usuário especificou.
"""

import asyncio
import os
import sys
import uuid

# Adicionar o diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.reels_maker import ReelsMaker, ReelsMakerConfig
from app.video_gen import VideoGeneratorConfig
from app.synth_gen import SynthConfig
from loguru import logger

# Configurar logging detalhado
logger.remove()
logger.add(sys.stderr, level="DEBUG")

PROMPT = """Quero um roteiro de video baseado nessa parada que achei no reddit:

5 Tipos de Pessoas Que Podem Arruinar Sua Vida - Resenha do Livro
Encontrei o livro 5 Tipos de Pessoas que Podem Arruinar Sua Vida: Identificando e Lidando com Narcisistas, Sociopatas e Outras Personalidades de Alto Conflito de Bill Eddy (psicoterapeuta, advogado, mediador e cofundador do High Conflict Institute) enquanto procurava livros sobre BPD na minha biblioteca local. Achei-o repleto de conceitos e técnicas claras e específicas.

O que são HCPs?
O livro contém informações sobre "personalidades de alto conflito" (HCPs) e como reconhecê-las e lidar com elas. Eddy define HCPs como um subconjunto de pessoas com transtornos de personalidade narcisista, borderline, antissocial, paranoide e histriônico.

Como reconhecer HCPs
Eddy apresenta o Método WEB: Observe as palavras da pessoa, suas próprias emoções sobre ela e o comportamento da pessoa.

Como lidar com HCPs
Eddy apresenta seu Método CARS: Conecte-se com empatia, Analise alternativas, Responda à desinformação, Estabeleça limites.

Conclusão
Já me beneficiei das novas maneiras de pensar que este livro proporcionou. Pretendo comprar o livro e consultá-lo regularmente."""

async def main():
    logger.info("=" * 60)
    logger.info("INICIANDO TESTE DE GERAÇÃO DE VÍDEO")
    logger.info("=" * 60)

    # Configuração de vídeo
    video_config = VideoGeneratorConfig(
        fontsize=60,
        stroke_color="#000000",  # Stroke escuro
        text_color="#ffffff",    # Texto branco
        stroke_width=1,
        font_name="Cinzel",
        subtitles_position="center,center",
        color_preset="valorgi",
        background_music_path="/Users/daviluis/Downloads/Cornfield_Chase_Interstellar_Soundtrack-643446-mobiles24.mp3",
    )

    # Configuração de síntese (voz)
    # Usando TikTok voice para teste (ElevenLabs SDK mudou e precisa de ajuste)
    synth_config = SynthConfig(
        voice_provider="tiktok",
        voice="br_005",  # Voz brasileira masculina do TikTok
    )

    # Configuração base
    config = ReelsMakerConfig(
        job_id=str(uuid.uuid4())[:8],
        video_type="motivational",
        prompt=PROMPT,
        script_duration=60,
        video_gen_config=video_config,
        synth_config=synth_config,
    )

    logger.info(f"Config: duration={config.script_duration}s")
    logger.info(f"Voice: provider={synth_config.voice_provider}, voice={synth_config.voice}")
    logger.info(f"Video config: preset={video_config.color_preset}, font={video_config.font_name}")

    # Criar engine
    engine = ReelsMaker(config)

    try:
        logger.info("Iniciando geração...")
        result = await engine.start()
        logger.info(f"SUCESSO! Vídeo gerado: {result.video_file_path}")
        return result
    except Exception as e:
        logger.error(f"ERRO NA GERAÇÃO: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(main())
