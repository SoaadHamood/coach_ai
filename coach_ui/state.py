import streamlit as st

def init_state() -> None:
    """
    Initializes all Streamlit session_state keys used across the app.
    Safe to call on every rerun (only sets defaults if missing).
    """
    defaults = {
        # -------------------------
        # Navigation / auth
        # -------------------------
        "page": "login",
        "logged_in": False,
        "login_email": "",
        "login_password": "",
        "post_call_sent": False,  # “sent to supervisor” UI state

        # -------------------------
        # Call lifecycle
        # -------------------------
        "active_call_id": None,
        "last_call_id": None,  # keep last call for post-call screen

        # -------------------------
        # Live session (existing mock timer/player state)
        # -------------------------
        "live_idx": 0,
        "call_seconds": 0,
        "live_play": False,
        "live_started": False,

        # -------------------------
        # NEW: Live transcription (HF Space backend)
        # -------------------------
        # Space config
        "space_id": "soaad34/callcoach-transcribe",  # default HF Space ID
        "lang_code": None,  # None=Auto, or "en"/"he"/"ar"

        # Audio/transcription state
        "live_transcript": [],  # list of tuples: [("Agent","..."), ("Customer","...")]
        "last_chunk_text": "",
        "live_last_error": "",

        # Optional: prevent double-processing the same recording
        "last_audio_hash": None,
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset_live_session() -> None:
    """
    Clears live-session data when starting a new call or ending a call.
    Keep call IDs separate (those are controlled by navigation).
    """
    st.session_state.live_idx = 0
    st.session_state.call_seconds = 0
    st.session_state.live_play = False
    st.session_state.live_started = False

    st.session_state.live_transcript = []
    st.session_state.last_chunk_text = ""
    st.session_state.live_last_error = ""
    st.session_state.last_audio_hash = None


def go(page: str) -> None:
    st.session_state.page = page
    st.rerun()
