import random
import typing
from typing import Literal
from app.utils.strings import log_attempt_number
from langchain_community.cache import SQLiteCache
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.globals import set_llm_cache
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, Field
from app.config import settings
from tenacity import retry, stop_after_attempt, wait_fixed
from app.config import llm_cache_path




class HashtagsSchema(BaseModel):
    """the hashtags response"""

    sentences: list[str] = Field(description="List of search terms for the sentence")


class SequentialVideoKeywordsSchema(BaseModel):
    """Sequential video keywords for each sentence"""

    keywords: list[str] = Field(
        description="List of English video search keywords, one per input sentence"
    )


class ImageLLMResponse(BaseModel):
    """the image prompt response"""

    image_prompts: list[str] = Field(description="List of MidJourney image prompt")


class ImagePromptResponses(BaseModel):
    image_prompts: list[str] = []
    sentences: list[str] = []


class StoryMiscResponse(BaseModel):
    """Additional properties extracted from the script or added to the video"""

    hook_title: str = Field(
        "",
        description="Generate a hook for the story/script. eg: what will happen if the hunter kills the dragon?  Eg 2. Is Free Will an Illusion?",
    )
    post_title: str = Field(
        "",
        description="Generate a social media post title, for the beginning of the story/script",
    )
    hashtags: list[str] = Field(
        [], description="Generate 8-12 relevant hashtags for the story/script"
    )


StoryPromptType = Literal["fantasy story", "motivational quote"] | str


class PromptGenerator:
    def __init__(self, test_mode: bool = False):
        set_llm_cache(SQLiteCache(database_path=f"{llm_cache_path}/llm_cache.db"))

        self.test_mode = test_mode
        self.model = ChatOpenAI(model=settings.OPENAI_MODEL_NAME)

    async def genarate_script(
        self,
        video_type: StoryPromptType,
        sentence_prompt: str,
        duration: str = "30 seconds",
    ) -> str:
        """generates a sentence from a prompt"""

        system_tmpl = """You are an expert short form video voiceover story/motivational writer for Instagram Reels and Youtube shorts."""

        user_tmpl = """
You are tasked with creating a voiceover for a '{video_type} scenario' about for the "Prompt" below. 
You must provide only the voiceover for the video, lasting around {duration} seconds.
Your response must only contain the voice over text without parenthesis or music effects tags

[(Prompt)]:
{sentence}
 """

        prompt = ChatPromptTemplate(
            [
                ("system", system_tmpl),
                ("human", user_tmpl),
            ]
        )

        self.model.temperature = random.uniform(0.5, 1.2)
        chain = prompt | self.model | StrOutputParser()

        logger.debug(f"Generating sentence from prompt: {sentence_prompt}")

        if self.test_mode:
            p = prompt.format(
                video_type=video_type, sentence=sentence_prompt, duration=duration
            )
            return p

        return await chain.ainvoke(
            {
                "sentence": sentence_prompt,
                "video_type": video_type,
                "duration": duration,
            }
        )

    async def generate_sentence(self, sentence: str, duration_seconds: int = 60, tts_model: str = "default") -> str:
        """generates a motivational script from a prompt with target duration

        Args:
            sentence: The prompt/topic for the script
            duration_seconds: Target duration in seconds
            tts_model: TTS model to optimize for ("eleven_v3", "eleven_multilingual_v2", or "default")
        """

        # Estimativa: ~150 palavras por minuto de narração = 2.5 palavras/segundo
        target_words = int(duration_seconds * 2.5)

        if tts_model == "eleven_v3":
            # Prompt otimizado para ElevenLabs v3 com tags de áudio
            tmpl = """You are a professional motivational narrator for Instagram Reels and TikTok videos.

Your task is to create an engaging voiceover script with AUDIO DIRECTION TAGS for ElevenLabs v3 text-to-speech.

=== AVAILABLE AUDIO TAGS ===

PAUSES (use these to create breathing room):
- [pause] - standard pause between ideas
- [short pause] - brief beat
- [long pause] - dramatic silence

EMOTIONS:
- [sighs] - reflective, tired, or accepting moments
- [whispers] - intimate, secret-sharing
- [excited] - enthusiastic, high energy
- [gasps] - surprise or realization
- [laughs] - humor, joy

DELIVERY TONES:
- [cheerfully] - upbeat delivery
- [playfully] - light, teasing
- [dramatic tone] - intense, important
- [resigned tone] - acceptance, giving in

RHYTHM CONTROL:
- [hesitates] - uncertainty, thinking
- [rushed] - urgency, excitement
- [drawn out] - emphasis, dramatic effect

TEXT FORMATTING:
- Use CAPS for words that need EMPHASIS
- Use "..." for natural breathing between phrases
- Use "?" to mark questions clearly

=== PACING RULES (CRITICAL) ===

1. ALWAYS add [pause] or [short pause] BEFORE questions
2. ALWAYS add [pause] AFTER impactful statements
3. Separate different ideas with pauses for natural flow
4. Don't let sentences run together - add breathing room
5. Questions should feel like questions - use questioning tone

=== EXAMPLE OF GOOD SCRIPT ===

"[sighs] Você acorda todo dia... [short pause] faz as mesmas coisas... e espera resultados diferentes. [pause] [whispers] Mas no fundo, você sabe que algo precisa mudar. [pause] [excited] E a boa notícia? [short pause] VOCÊ tem o poder de mudar TUDO... [dramatic tone] agora mesmo."

=== REQUIREMENTS ===

- Script must be approximately {target_words} words (for {duration_seconds}-second video)
- Write in Portuguese (Brazil)
- Use short, punchy sentences
- Include emotional hooks and powerful statements
- Use pauses generously - better to have MORE pauses than fewer
- Return ONLY the voiceover text with tags, nothing else

[(Prompt)]:
{sentence}
"""

        elif tts_model == "eleven_multilingual_v2":
            # Prompt otimizado para ElevenLabs v2 - usa pontuação estratégica para entonação
            tmpl = """You are a professional motivational narrator for Instagram Reels and TikTok videos.

Your task is to create an engaging voiceover script optimized for text-to-speech synthesis.

=== PUNCTUATION FOR BETTER INTONATION ===

The TTS engine interprets punctuation to control pacing and tone. Use these strategically:

PAUSES:
- Use "..." (reticências) for SMALL pauses and breathing room between phrases
- Use " — " (travessão com espaços) for DRAMATIC pauses before important statements
- Use "." to end declarative statements firmly

QUESTIONS (CRITICAL):
- ALWAYS put questions in their OWN sentence, separated from other text
- Add "..." BEFORE the question to create anticipation
- Example: "Você trabalha todo dia... — Mas pra quê?"

EMPHASIS:
- The TTS naturally emphasizes words after pauses
- Place important words after "..." or "—"

=== STRUCTURE RULES ===

1. NEVER combine a statement and question in the same sentence
2. ALWAYS add "..." before questions to signal tone change
3. Use "—" before revelations or powerful statements
4. Keep sentences short - easier for TTS to intonate correctly
5. End strong statements with "." not "..."

=== EXAMPLE OF GOOD SCRIPT ===

"Você acorda todo dia... faz as mesmas coisas... e espera resultados diferentes. — Mas por quê? ... Porque ninguém te ensinou que você pode mudar. Agora você sabe. — E o que vai fazer com isso?"

=== BAD EXAMPLE (avoid this) ===

"Você acorda todo dia e faz as mesmas coisas, já parou pra pensar por quê?"
(Question mixed with statement = TTS won't intonate the question correctly)

=== REQUIREMENTS ===

- Script must be approximately {target_words} words (for {duration_seconds}-second video)
- Write in Portuguese (Brazil)
- Use short, clear sentences
- Include emotional hooks and powerful statements
- Separate ALL questions into their own sentences
- Use "..." and "—" generously for pacing
- Return ONLY the voiceover text, nothing else

[(Prompt)]:
{sentence}
"""

        else:
            # Prompt padrão genérico (TikTok, outros)
            tmpl = """You are a professional motivational narrator for Instagram Reels and TikTok videos.

Your task is to create an engaging voiceover script based on the prompt below.

IMPORTANT REQUIREMENTS:
- The script must be approximately {target_words} words long (for a {duration_seconds}-second video)
- Write in a compelling, narrative style that keeps viewers engaged
- Use short, punchy sentences for impact
- Include emotional hooks and powerful statements
- DO NOT include any stage directions, music cues, or parenthetical notes
- Return ONLY the voiceover text, nothing else

[(Prompt)]:
{sentence}
"""

        prompt = ChatPromptTemplate.from_template(tmpl)

        chain = prompt | self.model | StrOutputParser()

        logger.debug(f"Generating script (~{target_words} words, tts_model={tts_model}) from prompt: {sentence}")
        return await chain.ainvoke({
            "sentence": sentence,
            "duration_seconds": duration_seconds,
            "target_words": target_words
        })

    async def generate_stock_image_keywords(self, sentence: str) -> HashtagsSchema:
        """generates search keywords from a sentence (legacy method)"""

        system_template = """
generate pexels.com search terms for the sentence below, the search keywords will be used to query an API:

{format_instructions}

[(examples)]:
Timing and letting go, Weakness and strength, Focus and hustle, Resonate with life etc...

[(sentence)]:
{sentence}
 """

        parser = PydanticOutputParser(pydantic_object=HashtagsSchema)
        prompt = ChatPromptTemplate.from_messages(
            messages=[("system", system_template), ("user", "{sentence}")]
        )
        prompt = prompt.partial(format_instructions=parser.get_format_instructions())

        chain = prompt | self.model | parser

        logger.debug(f"Generating sentence from prompt: {sentence}")
        return await chain.ainvoke({"sentence": sentence})

    async def generate_sequential_video_keywords(
        self, sentences: list[str]
    ) -> list[str]:
        """
        Generates one English video search keyword per sentence.

        Keywords are optimized for stock video APIs (Pexels, Pixabay):
        - Always in English (best API results)
        - Concrete and visual (what you'd actually see)
        - Sequential narrative flow (each keyword matches its sentence)

        Args:
            sentences: List of script sentences (can be in any language)

        Returns:
            List of English keywords, one per sentence
        """

        system_template = """You are a stock video search expert. Your task is to generate ONE English search keyword for EACH sentence provided.

=== CRITICAL RULES ===

1. OUTPUT IN ENGLISH ONLY - Stock video APIs work best with English keywords
2. ONE KEYWORD PER SENTENCE - You must return exactly {sentence_count} keywords
3. CONCRETE & VISUAL - Keywords must describe something you can actually SEE in a video
4. KEEP IT SIMPLE - 1-3 words max per keyword

=== WHAT MAKES A GOOD KEYWORD ===

GOOD (concrete, visual):
- "frog pond" (you can see a frog)
- "person walking city" (you can see a person walking)
- "sunset beach" (you can see a sunset)
- "businessman thinking" (you can see a person)
- "rain window" (you can see rain on a window)

BAD (abstract, won't find videos):
- "success" (too abstract)
- "letting go" (emotional concept, not visual)
- "resilience" (can't see this)
- "timing" (not visual)
- "inner peace" (not visual)

=== TRANSLATION EXAMPLES ===

If sentence is in Portuguese about "sapo" → keyword: "frog"
If sentence is about "sucesso" → keyword: "businessman celebration" (visual representation)
If sentence is about "medo" → keyword: "person afraid" or "dark room" (visual representation)

=== INPUT SENTENCES ===

{sentences}

{format_instructions}

Remember: Return EXACTLY {sentence_count} keywords, in the SAME ORDER as the sentences."""

        parser = PydanticOutputParser(pydantic_object=SequentialVideoKeywordsSchema)

        # Format sentences with numbers for clarity
        formatted_sentences = "\n".join(
            f"{i+1}. {s}" for i, s in enumerate(sentences)
        )

        prompt = ChatPromptTemplate.from_messages(
            messages=[("system", system_template)]
        )
        prompt = prompt.partial(
            format_instructions=parser.get_format_instructions(),
            sentence_count=len(sentences),
        )

        chain = prompt | self.model | parser

        logger.debug(f"Generating {len(sentences)} sequential video keywords")
        result = await chain.ainvoke({"sentences": formatted_sentences})

        # Validate count matches
        if len(result.keywords) != len(sentences):
            logger.warning(
                f"Keyword count mismatch: expected {len(sentences)}, got {len(result.keywords)}. "
                "Padding or truncating..."
            )
            # Pad with generic keywords if too few
            while len(result.keywords) < len(sentences):
                result.keywords.append("nature landscape")
            # Truncate if too many
            result.keywords = result.keywords[:len(sentences)]

        logger.info(f"Generated sequential keywords: {result.keywords}")
        return result.keywords

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5), after=log_attempt_number) # type: ignore
    async def sentences_to_images(
        self,
        sentences: list[str],
        style: str,
    ) -> ImagePromptResponses:
        user_template = """
You are a master of crafting detailed visual narratives. Your task is to generate descriptions of scenes for an animator, based on a story. Each scene description will guide the animator in creating the corresponding visual frames for the video.
Respond only with vivid, intricate descriptions of the scenes. Focus exclusively on providing the animator with everything they need to visualize characters, locations, and concepts clearly and consistently.

For each paragraph, you must:
- Describe a new scene, environment, or characters, while preserving continuity with recurring elements and any significant objects in meticulous detail
- Use keywords and descriptive phrases rather than full sentences.
- Do not include titles, names, or captions.

Examples:
- Caesar (tall, muscular frame, with a sharp jawline and piercing brown eyes, wearing a laurel wreath, ornate armor with gold detailing, and a crimson cape flowing in the wind), standing on a grassy hilltop under a cloudy sky.
- A small, dimly lit room with worn wooden furniture, a single flickering candle casting shadows on the cracked walls, and an old woman (slightly hunched, wearing a faded shawl, with wisps of gray hair escaping from under a knitted cap) gazing thoughtfully out of a tiny window.
- A bustling marketplace, with colorful stalls lining the cobblestone streets, vendors shouting offers to passersby, and a young boy (dressed in ragged clothes, with tousled hair and bright green eyes) darting through the crowd, clutching a loaf of bread.

You will be penalized if descriptions are incomplete or lack detail, or if any additional text (headings, etc.) is included.
The visual narrative should be rich and immersive, allowing the animator to seamlessly create MidJourney-style artwork from your descriptions.

{format_instructions}

[(Paragraphs)]:
{sentences}

You must generate a total of {total_count} descriptions, each preserving a coherent visual narrative and maintaining distinct character features throughout.
"""

        parser = PydanticOutputParser(pydantic_object=ImageLLMResponse)

        formated_sentences = "- " + "\n- ".join(sentences)

        prompt = ChatPromptTemplate.from_messages(messages=[("system", user_template)])
        prompt = prompt.partial(
            format_instructions=parser.get_format_instructions(),
            total_count=len(sentences),
        )

        chain = prompt | self.model | parser

        logger.debug("Generating image prompts")
        data = await chain.ainvoke({"sentences": formated_sentences, "style": style})

        if len(data.image_prompts) != len(sentences):
            raise ValueError(
                f"Expected {len(sentences)} image prompts, got {len(data.image_prompts)}"
            )

        logger.info(f"Generated {len(data.image_prompts)} image prompts")
        logger.debug(f"image prompts: {data.image_prompts}")
        return ImagePromptResponses(
            sentences=sentences, image_prompts=data.image_prompts
        )

    async def generate_video_misc_info(self, script: str) -> StoryMiscResponse:
        """generates video misc info from a script"""

        system_template = """
Extracts relevant information from the script below.

{format_instructions}

[(Script)]:
{script}
"""

        logger.debug("Generating video misc info")

        parser = PydanticOutputParser(pydantic_object=StoryMiscResponse)

        prompt = ChatPromptTemplate.from_messages(
            messages=[("system", system_template)]
        )
        prompt = prompt.partial(
            format_instructions=parser.get_format_instructions(),
        )

        chain = prompt | self.model | parser
        data = await chain.ainvoke({"script": script})
        data = typing.cast(StoryMiscResponse, data)

        # removed # from hashtags - we only need the tag for social media
        data.hashtags = [
            tag if not tag.startswith("#") else tag.replace("#", "")
            for tag in data.hashtags
        ]

        return data
