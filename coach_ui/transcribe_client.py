"""
coach_ui/transcribe_client.py

HF Space transcription client with:
- Streamlit resource caching (keeps one gradio Client per Space ID)
- Retries + backoff (reduces "read operation timed out" pain)
- Small, safe normalization of outputs
- Temp file cleanup always
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st
from gradio_client import Client, handle_file

TMP_DIR = Path("tmp_audio")
TMP_DIR.mkdir(parents=True, exist_ok=True)


def sha1_bytes(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()


@st.cache_resource(show_spinner=False)
def get_client(space_id: str) -> Client:
    """
    Cache the Gradio client across Streamlit reruns.
    This reduces reconnect overhead and improves stability on HF Spaces.
    """
    return Client(space_id.strip())


def _normalize_lang(lang_code: Optional[str]) -> str:
    if not lang_code:
        return "Auto"
    lang = str(lang_code).strip()
    return "Auto" if lang.lower() == "auto" else lang


def _normalize_out(out: Any) -> Dict[str, Any]:
    """
    Normalize gradio output into a dict with at least {"text": "..."}.
    Accepts dict/str/tuple/list gracefully.
    """
    if isinstance(out, dict):
        # common keys: "text", sometimes others depending on the backend
        if "text" in out:
            return out
        # If backend returns something like {"transcript": "..."}
        for k in ("transcript", "output", "prediction"):
            if k in out:
                return {"text": str(out[k])}
        return {"text": str(out)}

    if isinstance(out, (list, tuple)) and out:
        # Often gradio returns a tuple with the text as first item
        return {"text": str(out[0])}

    return {"text": "" if out is None else str(out)}


def transcribe_via_space(space_id: str, audio_bytes: bytes, lang_code: str | None) -> Dict[str, Any]:
    """
    Transcribe a WAV bytes payload by calling a Hugging Face Space Gradio endpoint.

    Args:
        space_id: "username/space-name"
        audio_bytes: WAV bytes
        lang_code: None or language code; "Auto" if None

    Returns:
        dict with at least {"text": "..."} on success

    Raises:
        RuntimeError if all retries fail
    """
    if not space_id or not space_id.strip():
        raise ValueError("HF Space ID is empty. Expected format: username/space-name")

    if not audio_bytes:
        return {"text": ""}

    tmp_path = TMP_DIR / f"chunk_{sha1_bytes(audio_bytes)}.wav"
    tmp_path.write_bytes(audio_bytes)

    client = get_client(space_id)
    lang = _normalize_lang(lang_code)

    # HF-free-tier resilience
    max_tries = 3
    base_backoff = 1.25  # seconds (scaled by attempt)

    try:
        last_err: Exception | None = None

        for attempt in range(1, max_tries + 1):
            try:
                # NOTE: This assumes your backend expects (audio_file, lang) in that order.
                out = client.predict(handle_file(str(tmp_path)), lang)
                return _normalize_out(out)

            except Exception as e:
                last_err = e
                # Exponential-ish backoff
                time.sleep(base_backoff * attempt)

        raise RuntimeError(f"Remote transcription failed after {max_tries} tries: {last_err}") from last_err

    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
