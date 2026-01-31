"""Gemini AI service for metadata generation."""

import json
import os
from pathlib import Path
from typing import Optional

from google import genai

from ..config import get_gemini_api_key, load_config


class GeminiService:
    """Service for generating video metadata using Gemini AI."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or get_gemini_api_key()
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        """Get or create Gemini client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "Gemini API key not configured. "
                    "Run 'tubecast setup' or set GEMINI_API_KEY environment variable."
                )
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate_metadata(
        self,
        video_filename: str,
        context: str = "",
        model: Optional[str] = None,
    ) -> dict:
        """Generate video metadata from filename and optional context."""
        config = load_config()
        model = model or config.get("gemini_model", "gemini-2.5-flash")

        prompt = f"""
You are a YouTube SEO expert. Generate optimized metadata for a video upload.

Video filename: {video_filename}
{f"Additional context: {context}" if context else ""}

Generate a JSON object with:
1. "title": Catchy, SEO-friendly title (max 100 chars, no clickbait)
2. "description": Detailed description with keywords (300-500 words)
   - Include timestamps placeholder if it seems like a long video
   - Add relevant hashtags at the end
   - Include call to action (like, subscribe, comment)
3. "tags": List of 10-15 relevant keywords/phrases for discoverability

Return ONLY valid JSON, no markdown or explanation.

Example format:
{{"title": "...", "description": "...", "tags": ["tag1", "tag2", ...]}}
""".strip()

        response = self.client.models.generate_content(
            model=model,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )

        text = response.text
        if not text:
            raise ValueError("Empty response from Gemini")

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            json_match = text.find("{")
            json_end = text.rfind("}") + 1
            if json_match != -1 and json_end > json_match:
                return json.loads(text[json_match:json_end])
            raise ValueError(f"Failed to parse Gemini response: {text}")

    def enhance_description(
        self,
        title: str,
        description: str,
        model: Optional[str] = None,
    ) -> str:
        """Enhance an existing video description."""
        config = load_config()
        model = model or config.get("gemini_model", "gemini-2.5-flash")

        prompt = f"""
Enhance this YouTube video description for better SEO and engagement.
Keep the same meaning but make it more professional and discoverable.

Title: {title}
Current description: {description}

Requirements:
- Add relevant hashtags
- Include a call to action
- Use natural keywords
- Keep it engaging and informative
- Max 5000 characters

Return only the enhanced description, no explanation.
""".strip()

        response = self.client.models.generate_content(
            model=model,
            contents=prompt,
        )

        return response.text or description

    def generate_tags(
        self,
        title: str,
        description: str,
        model: Optional[str] = None,
    ) -> list[str]:
        """Generate tags for a video based on title and description."""
        config = load_config()
        model = model or config.get("gemini_model", "gemini-2.5-flash")

        prompt = f"""
Generate 15 YouTube tags for this video to maximize discoverability.

Title: {title}
Description excerpt: {description[:500]}

Requirements:
- Mix of broad and specific tags
- Include long-tail keywords
- No hashtags, just plain keywords
- Each tag max 30 characters

Return as a JSON array of strings, nothing else.
Example: ["tag1", "tag2", "tag3"]
""".strip()

        response = self.client.models.generate_content(
            model=model,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )

        text = response.text
        if not text:
            return []

        try:
            tags = json.loads(text)
            if isinstance(tags, list):
                return [str(t) for t in tags[:15]]
        except json.JSONDecodeError:
            pass

        return []


def is_gemini_available() -> bool:
    """Check if Gemini API is configured and available."""
    api_key = get_gemini_api_key()
    if not api_key:
        return False

    try:
        client = genai.Client(api_key=api_key)
        client.models.generate_content(
            model="gemini-2.5-flash",
            contents="test",
        )
        return True
    except Exception:
        return False
