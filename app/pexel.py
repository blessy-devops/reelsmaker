import os
from loguru import logger
import requests


async def search_for_stock_videos(query: str, limit: int, min_dur: int) -> list[str]:
    """
    Busca vídeos no Pexels.

    Args:
        query: Termo de busca
        limit: Quantidade máxima de vídeos para retornar
        min_dur: Duração mínima do vídeo em segundos

    Returns:
        Lista de URLs de vídeos (maior resolução disponível)
    """
    headers = {
        "Authorization": os.getenv("PEXELS_API_KEY"),
    }

    # Removido filtro orientation=portrait para permitir vídeos horizontais também
    # O video_gen.py faz scale + crop inteligente para adaptar qualquer orientação
    # per_page máximo da API Pexels é 80
    per_page = min(limit, 80)
    qurl = f"https://api.pexels.com/videos/search?query={query}&per_page={per_page}"

    try:
        r = requests.get(qurl, headers=headers, timeout=30)
        r.raise_for_status()
        response = r.json()
    except requests.RequestException as e:
        logger.error(f"Pexels API error: {e}")
        return []

    video_urls = []

    videos = response.get("videos", [])
    for video_data in videos:
        if len(video_urls) >= limit:
            break

        # Verificar duração mínima
        if video_data.get("duration", 0) < min_dur:
            continue

        # Encontrar a melhor resolução
        video_files = video_data.get("video_files", [])
        best_url = ""
        best_resolution = 0

        for video_file in video_files:
            # Pegar apenas links válidos
            link = video_file.get("link", "")
            if ".com/video-files" not in link:
                continue

            width = video_file.get("width", 0)
            height = video_file.get("height", 0)
            resolution = width * height

            if resolution > best_resolution:
                best_resolution = resolution
                best_url = link

        if best_url:
            video_urls.append(best_url)

    logger.debug(f"Pexels search '{query}': found {len(video_urls)} videos (requested {limit})")
    return video_urls
