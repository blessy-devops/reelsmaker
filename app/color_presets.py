"""
Color grading presets para vídeos.
Cada preset define filtros FFmpeg que são aplicados antes das legendas.
"""

from dataclasses import dataclass
from typing import Callable
import ffmpeg


@dataclass
class ColorPreset:
    """Define um preset de color grading."""
    name: str
    description: str
    # Valores normalizados (-100 a +100, onde 0 = neutro)
    temperature: int = 0      # Temperatura de cor (-100 frio, +100 quente)
    hue: int = 0              # Matiz (-180 a +180 graus)
    saturation: int = 0       # Saturação (-100 a +100)
    brightness: int = 0       # Brilho (-100 a +100)
    contrast: int = 0         # Contraste (-100 a +100)
    shadows: int = 0          # Sombras (-100 mais escuro, +100 mais claro)
    vignette: int = 0         # Vinheta (0 = sem, 100 = máximo)


def apply_color_preset(clip, preset: ColorPreset):
    """
    Aplica um preset de color grading a um clip FFmpeg.
    Usa apenas filtros básicos e estáveis para evitar erros.

    Args:
        clip: Stream FFmpeg
        preset: ColorPreset com as configurações

    Returns:
        Stream FFmpeg com filtros aplicados
    """
    if preset.name == "none":
        return clip

    # Aplicar ajustes de cor usando eq (equalizer) - FILTRO MAIS ESTÁVEL
    # eq aceita: brightness (-1 a 1), contrast (0 a 2), saturation (0 a 3), gamma (0.1 a 10)

    # Converter valores de -100/+100 para escala do FFmpeg
    brightness = preset.brightness / 100  # -1 a 1
    contrast = 1 + (preset.contrast / 100)  # 0 a 2 (1 = normal)
    saturation = 1 + (preset.saturation / 100)  # 0 a 2 (1 = normal)

    # Gamma para simular shadows (menor gamma = sombras mais escuras)
    gamma = 1 - (preset.shadows / 200)  # 0.5 a 1.5
    gamma = max(0.5, min(1.5, gamma))

    # Aplicar tudo em um único filtro eq (mais eficiente e estável)
    clip = clip.filter(
        "eq",
        brightness=brightness,
        contrast=contrast,
        saturation=saturation,
        gamma=gamma
    )

    # Aplicar ajuste de hue (matiz) + saturação adicional via hue
    # Isso também simula temperatura de cor de forma simplificada
    if preset.hue != 0 or preset.temperature != 0:
        # Converter de -100/+100 para graus (-180 a +180)
        hue_degrees = preset.hue * 1.8
        # Temperatura afeta levemente o hue (frio = azulado, quente = amarelado)
        hue_degrees += preset.temperature * 0.3
        clip = clip.filter("hue", h=hue_degrees)

    # Vinheta simplificada
    if preset.vignette > 0:
        vignette_angle = preset.vignette / 100 * 0.4  # 0 a 0.4 (mais sutil)
        clip = clip.filter("vignette", angle=vignette_angle)

    return clip


# ============================================================
# PRESETS DISPONÍVEIS
# ============================================================

PRESETS = {
    "none": ColorPreset(
        name="none",
        description="Sem color grading",
    ),

    "valorgi": ColorPreset(
        name="valorgi",
        description="Look cinematográfico clean e contrastado",
        temperature=-10,    # Levemente frio (era -20)
        hue=-5,             # Quase neutro (era -20, causava roxo)
        saturation=-10,     # Levemente dessaturado (era -20)
        brightness=-5,      # Levemente escuro (era -15)
        contrast=15,        # Mais contraste
        shadows=-5,         # Sombras suaves (era -10)
        vignette=10,        # Vinheta sutil (era 15)
    ),

    "warm_vintage": ColorPreset(
        name="warm_vintage",
        description="Look quente e nostálgico",
        temperature=25,
        hue=5,
        saturation=-10,
        brightness=5,
        contrast=10,
        shadows=5,
        vignette=20,
    ),

    "cold_cinematic": ColorPreset(
        name="cold_cinematic",
        description="Look frio estilo filme",
        temperature=-30,
        hue=-10,
        saturation=-15,
        brightness=-10,
        contrast=20,
        shadows=-15,
        vignette=25,
    ),

    "high_contrast": ColorPreset(
        name="high_contrast",
        description="Alto contraste vibrante",
        temperature=0,
        hue=0,
        saturation=15,
        brightness=0,
        contrast=30,
        shadows=-20,
        vignette=10,
    ),

    "moody_dark": ColorPreset(
        name="moody_dark",
        description="Escuro e atmosférico",
        temperature=-15,
        hue=-5,
        saturation=-25,
        brightness=-25,
        contrast=20,
        shadows=-25,
        vignette=30,
    ),
}


def get_preset(name: str) -> ColorPreset:
    """Retorna um preset pelo nome."""
    return PRESETS.get(name.lower(), PRESETS["none"])


def get_preset_names() -> list[str]:
    """Retorna lista de nomes de presets disponíveis."""
    return list(PRESETS.keys())
