"""Configuration module for Project Aero.

Loads and validates environment variables using Pydantic Settings.
Centralizes latency budgets, voice parameters, and model configurations.
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings with strict typing and validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LiveKit Cloud ---
    LIVEKIT_URL: str = Field(..., description="LiveKit Cloud WebSocket URL")
    LIVEKIT_API_KEY: str = Field(..., description="LiveKit API Key")
    LIVEKIT_API_SECRET: str = Field(..., description="LiveKit API Secret")

    # --- Deepgram (STT) ---
    DEEPGRAM_API_KEY: str = Field(..., description="Deepgram API Key for Nova-3 streaming")
    DEEPGRAM_MODEL: str = Field(default="nova-3", description="Deepgram STT model")

    # --- Cartesia (TTS) ---
    CARTESIA_API_KEY: str = Field(..., description="Cartesia API Key")
    CARTESIA_MODEL_ID: str = Field(default="sonic-3.6", description="Cartesia model identifier")
    CARTESIA_VOICE_ID: str = Field(
        default="db6b0ed5-d5d3-463d-ae85-518a07d3c2b4",
        description="Cartesia conversational voice UUID",
    )
    CARTESIA_SAMPLE_RATE: int = Field(default=24000, description="Audio sample rate (Hz)")

    # --- Google Gemini (LLM) ---
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API Key from aistudio.google.com")
    GEMINI_MODEL: str = Field(default="gemini-3.5-flash-lite", description="Gemini LLM model")
    GEMINI_TEMPERATURE: float = Field(default=0.2, description="Sampling temperature for speed")

    # --- OpenAI (Fallback LLM & Eval Judge) ---
    OPENAI_API_KEY: str = Field(..., description="OpenAI API Key for fallback and evaluation")
    OPENAI_PROJECT_ID: Optional[str] = Field(default=None, description="OpenAI project identifier")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini", description="OpenAI fallback model")

    # --- Agent Persona & Room ---
    AGENT_NAME: str = Field(default="Aria", description="Voice agent persona name")
    AGENT_ROOM_PREFIX: str = Field(default="aero-room", description="Default prefix for rooms")

    # --- VAD & Latency Target Budgets (ms) ---
    VAD_INTERRUPTION_THRESHOLD_MS: int = Field(
        default=300,
        description="Speech duration required before triggering barge-in interruption",
    )
    VAD_ENDPOINTING_PAUSE_MS: int = Field(
        default=450,
        description="Silence duration required before considering user turn complete",
    )
    TARGET_TOTAL_ROUNDTRIP_MS: int = Field(
        default=640,
        description="Target maximum turnaround time from speech end to initial audio playback",
    )

    # --- Evaluation ---
    ENABLE_BENCHMARKS: bool = Field(default=False, description="Enable automated benchmark reporting")
    EVAL_JUDGE_MODEL: str = Field(default="gpt-4o-mini", description="LLM judge model for evaluations")


# Global singleton settings instance
settings = Settings()
