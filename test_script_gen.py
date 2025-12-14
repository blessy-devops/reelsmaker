#!/usr/bin/env python3
"""
Teste isolado do gerador de roteiros.
Uso: python3 test_script_gen.py "seu prompt aqui" [duração_segundos] [--v3|--v2]

--v3: Gera com tags de áudio do ElevenLabs v3
--v2: Gera com pontuação estratégica para ElevenLabs v2
(sem flag): Prompt padrão genérico
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.prompt_gen import PromptGenerator
from loguru import logger

# Configurar logging
logger.remove()
logger.add(sys.stderr, level="INFO")


async def generate_script(prompt: str, duration: int = 60, tts_model: str = "default"):
    """Gera um roteiro a partir de um prompt"""

    generator = PromptGenerator()

    model_labels = {
        "eleven_v3": "ElevenLabs v3 (com tags de áudio)",
        "eleven_multilingual_v2": "ElevenLabs v2 (com pontuação estratégica)",
        "default": "Padrão (genérico)"
    }

    print(f"\n{'='*60}")
    print(f"PROMPT: {prompt[:100]}..." if len(prompt) > 100 else f"PROMPT: {prompt}")
    print(f"DURAÇÃO ALVO: {duration} segundos (~{int(duration * 2.5)} palavras)")
    print(f"MODO: {model_labels.get(tts_model, tts_model)}")
    print(f"{'='*60}\n")

    script = await generator.generate_sentence(prompt, duration_seconds=duration, tts_model=tts_model)

    word_count = len(script.split())
    estimated_duration = word_count / 2.5

    print("ROTEIRO GERADO:")
    print("-" * 40)
    print(script)
    print("-" * 40)
    print(f"\nESTATÍSTICAS:")
    print(f"  Palavras: {word_count}")
    print(f"  Duração estimada: {estimated_duration:.1f}s")
    print(f"  Alvo: {duration}s")

    if tts_model == "eleven_v3":
        # Contar tags v3
        import re
        tags = re.findall(r'\[[\w\s]+\]', script)
        ellipsis_count = script.count('...')
        caps_words = re.findall(r'\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}\b', script)
        print(f"\n  TAGS V3 ENCONTRADAS:")
        print(f"    Tags de emoção: {len(tags)} ({', '.join(set(tags)) if tags else 'nenhuma'})")
        print(f"    Pausas (...): {ellipsis_count}")
        print(f"    Palavras em CAPS: {len(caps_words)}")

    elif tts_model == "eleven_multilingual_v2":
        # Contar elementos de pontuação v2
        ellipsis_count = script.count('...')
        dash_count = script.count('—')
        question_count = script.count('?')
        print(f"\n  PONTUAÇÃO V2 ENCONTRADA:")
        print(f"    Reticências (...): {ellipsis_count}")
        print(f"    Travessões (—): {dash_count}")
        print(f"    Perguntas (?): {question_count}")

    return script


async def generate_search_terms(script: str):
    """Gera termos de busca para vídeos do Pexels"""

    generator = PromptGenerator()

    print(f"\n{'='*60}")
    print("GERANDO TERMOS DE BUSCA PARA PEXELS...")
    print(f"{'='*60}\n")

    result = await generator.generate_stock_image_keywords(script)

    print("TERMOS DE BUSCA:")
    for term in result.sentences:
        print(f"  - {term}")

    return result.sentences


if __name__ == "__main__":
    # Verificar flags
    tts_model = "default"
    if "--v3" in sys.argv:
        tts_model = "eleven_v3"
    elif "--v2" in sys.argv:
        tts_model = "eleven_multilingual_v2"

    args = [a for a in sys.argv[1:] if a not in ["--v3", "--v2"]]

    if len(args) < 1:
        # Prompt padrão para teste
        prompt = """Quero um roteiro de video baseado nessa parada que achei no reddit:

5 Tipos de Pessoas Que Podem Arruinar Sua Vida - Resenha do Livro
Encontrei o livro 5 Tipos de Pessoas que Podem Arruinar Sua Vida de Bill Eddy.
O livro identifica personalidades de alto conflito (HCPs) e como lidar com elas.
Método WEB: Observe palavras, emoções e comportamento.
Método CARS: Conecte-se com empatia, Analise alternativas, Responda à desinformação, Estabeleça limites."""
        duration = 60
    else:
        prompt = args[0]
        duration = int(args[1]) if len(args) > 1 else 60

    # Gerar roteiro
    script = asyncio.run(generate_script(prompt, duration, tts_model=tts_model))

    # Gerar termos de busca
    asyncio.run(generate_search_terms(script))
