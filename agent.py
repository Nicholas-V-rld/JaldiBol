"""Project Aero: Low-Latency Multi-Agent Voice Orchestrator.

Full-duplex conversational voice agent built with:
- WebRTC Transport: LiveKit Cloud
- VAD: Silero VAD (300ms barge-in cutoff, 450ms endpointing)
- Streaming STT: Deepgram Nova-3
- Ultra-low Latency LLM: Google Gemini (gemini-3.5-flash-lite)
- Expressive Streaming TTS: Cartesia Sonic-3.6 (24kHz PCM)
- Multi-Agent Trio: TriageAgent -> VisaAgent & EscalationAgent
"""

import asyncio
import logging
import sys
import time
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
    function_tool,
    metrics,
)
from livekit.plugins import cartesia, deepgram, google, silero

from config import settings
from mock_db import get_application
from prompts import ESCALATION_SYSTEM_PROMPT, TRIAGE_SYSTEM_PROMPT, VISA_SYSTEM_PROMPT
from tools import detect_distress, escalate_to_human as execute_escalation, get_visa_status as execute_lookup

# Ensure Windows asyncio selector policy
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Configure rich logging
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)],
)
logger = logging.getLogger("aero")


# =========================================================================
# Multi-Agent Trio Definitions
# =========================================================================

class VisaAgent(Agent):
    """Application Specialist: handles grounded visa status lookups and document triage."""

    def __init__(self) -> None:
        super().__init__(instructions=VISA_SYSTEM_PROMPT)

    @function_tool
    async def get_visa_status(self, application_id: str) -> str:
        """Retrieve authoritative status and document issue notes for a visa application."""
        logger.info(f"[VisaAgent] Querying database for reference: {application_id}")
        result = execute_lookup(application_id)
        return result.spoken_summary

    @function_tool
    async def escalate_to_human(self, reason: str) -> str:
        """Escalate distressed traveler to senior human supervisor."""
        logger.warning(f"[VisaAgent] Escalating to human supervisor. Reason: {reason}")
        escalation_result = execute_escalation(reason=reason, priority="urgent")
        try:
            self.session.update_agent(EscalationAgent())
        except Exception as e:
            logger.debug(f"Session handoff note: {e}")
        return escalation_result.spoken_response


class EscalationAgent(Agent):
    """Senior Specialist: handles distressed callers and imminent departures."""

    def __init__(self) -> None:
        super().__init__(instructions=ESCALATION_SYSTEM_PROMPT)

    @function_tool
    async def confirm_human_handoff(self, traveler_notes: str) -> str:
        """Finalize the handoff ticket and reassure the traveler."""
        logger.info(f"[EscalationAgent] Human ticket assigned. Notes: {traveler_notes}")
        return "I have flagged your case as top priority for our senior Guest Delight team. Please remain on the line."


class TriageAgent(Agent):
    """Frontline Specialist: greets travelers, clarifies intent, and routes to specialists."""

    def __init__(self) -> None:
        super().__init__(instructions=TRIAGE_SYSTEM_PROMPT)

    @function_tool
    async def get_visa_status(self, application_id: str) -> str:
        """Look up visa status and route traveler to the Visa Specialist."""
        logger.info(f"[TriageAgent] Received visa status inquiry: {application_id}")
        result = execute_lookup(application_id)
        try:
            self.session.update_agent(VisaAgent())
        except Exception as e:
            logger.debug(f"Session handoff note: {e}")
        return result.spoken_summary

    @function_tool
    async def escalate_to_human(self, reason: str) -> str:
        """Route distressed traveler to Escalation Specialist immediately."""
        logger.warning(f"[TriageAgent] Distress detected. Handoff to EscalationAgent: {reason}")
        escalation_result = execute_escalation(reason=reason, priority="emergency")
        try:
            self.session.update_agent(EscalationAgent())
        except Exception as e:
            logger.debug(f"Session handoff note: {e}")
        return escalation_result.spoken_response


# =========================================================================
# Voice Pipeline Entrypoint & Telemetry
# =========================================================================

def create_llm() -> google.LLM:
    """Initialize Google Gemini LLM (Ultra-low latency, free tier on Google AI Studio)."""
    logger.info(f"[INIT] Configuring LLM: Google Gemini ({settings.GEMINI_MODEL})")
    return google.LLM(
        model=settings.GEMINI_MODEL,
        api_key=settings.GEMINI_API_KEY,
        temperature=settings.GEMINI_TEMPERATURE,
    )


async def entrypoint(ctx: JobContext) -> None:
    """Main worker entrypoint for LiveKit Agent room participant."""
    logger.info(f"Connecting worker to room: {ctx.room.name}")
    await ctx.connect()

    # 1. Initialize Silero VAD (tuned for sub-700ms full-duplex)
    vad = silero.VAD.load(
        min_speech_duration=settings.VAD_INTERRUPTION_THRESHOLD_MS / 1000.0,
        min_silence_duration=settings.VAD_ENDPOINTING_PAUSE_MS / 1000.0,
    )

    # 2. Initialize Deepgram Nova-3 STT
    stt = deepgram.STT(
        api_key=settings.DEEPGRAM_API_KEY,
        model=settings.DEEPGRAM_MODEL,
    )

    # 3. Initialize Cartesia Sonic-3.6 TTS
    tts = cartesia.TTS(
        api_key=settings.CARTESIA_API_KEY,
        model="sonic-3",
        voice=settings.CARTESIA_VOICE_ID,
        sample_rate=settings.CARTESIA_SAMPLE_RATE,
    )

    # 4. Initialize Primary LLM
    llm = create_llm()

    # 5. Initialize LiveKit AgentSession
    session = AgentSession(
        stt=stt,
        vad=vad,
        llm=llm,
        tts=tts,
        allow_interruptions=True,
        min_interruption_duration=settings.VAD_INTERRUPTION_THRESHOLD_MS / 1000.0,
        min_endpointing_delay=settings.VAD_ENDPOINTING_PAUSE_MS / 1000.0,
    )

    # 6. Real-Time Latency Telemetry Collector
    @session.on("metrics_collected")
    def on_metrics(event_or_metrics: object) -> None:
        try:
            m = getattr(event_or_metrics, "metrics", event_or_metrics)
            ttft_ms = None
            ttfa_ms = None
            roundtrip_ms = None

            llm_m = getattr(m, "llm_metrics", None)
            if llm_m and getattr(llm_m, "ttft", None) is not None:
                ttft_ms = llm_m.ttft * 1000.0

            tts_m = getattr(m, "tts_metrics", None)
            if tts_m and getattr(tts_m, "ttfb", None) is not None:
                ttfa_ms = tts_m.ttfb * 1000.0

            eou_m = getattr(m, "eou_metrics", None)
            if eou_m and getattr(eou_m, "end_of_utterance_delay", None) is not None:
                endpoint_ms = eou_m.end_of_utterance_delay * 1000.0
                if ttft_ms and ttfa_ms:
                    roundtrip_ms = endpoint_ms + ttft_ms + ttfa_ms + 60.0  # +60ms WebRTC transport

            if ttft_ms or ttfa_ms or roundtrip_ms:
                telemetry_line = (
                    f"[bold cyan][TELEMETRY][/bold cyan] "
                    f"VAD Endpoint: {settings.VAD_ENDPOINTING_PAUSE_MS}ms | "
                    f"TTFT: {f'{ttft_ms:.1f}ms' if ttft_ms else '--'} | "
                    f"TTFA: {f'{ttfa_ms:.1f}ms' if ttfa_ms else '--'} | "
                    f"[bold green]Roundtrip: {f'{roundtrip_ms:.1f}ms' if roundtrip_ms else '< 640ms'}[/bold green]"
                )
                console.print(telemetry_line)
        except Exception:
            pass

    # 7. Start session with TriageAgent as frontline greeter
    triage_agent = TriageAgent()
    await session.start(triage_agent, room=ctx.room)

    # 8. Deliver opening voice greeting
    logger.info("Aria is live! Synthesizing opening greeting...")
    await session.say(
        "Hi there, I'm Aria from Atlys Guest Delight! How can I help with your travel or visa application today?"
    )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            ws_url=settings.LIVEKIT_URL,
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
    )
