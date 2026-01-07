import hashlib
import os
from datetime import datetime
from pathlib import Path

import streamlit as st
from audio_recorder_streamlit import audio_recorder
from gradio_client import Client, handle_file


# =========================
# Config
# =========================
APP_TITLE = "LiveCoach — Record & Transcribe (HF Space Backend)"
SPACE_ID_DEFAULT = "soaad34/callcoach-transcribe"

TMP_DIR = Path("tmp_audio")
SAVE_DIR = Path("recordings")
TMP_DIR.mkdir(parents=True, exist_ok=True)
SAVE_DIR.mkdir(parents=True, exist_ok=True)

# Safety cap to avoid huge uploads
MAX_AUDIO_BYTES = 3_000_000  # ~3MB


# =========================
# Helpers
# =========================
def sha1_bytes(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()


def write_wav_bytes(audio_bytes: bytes, out_path: Path) -> None:
    out_path.write_bytes(audio_bytes)


@st.cache_resource(show_spinner=False)
def get_space_client(space_id: str) -> Client:
    # Cached across reruns; avoids reconnect overhead
    return Client(space_id)


def transcribe_via_space(client: Client, wav_path: Path, lang_code: str | None) -> dict:
    # Our Space expects: (Audio filepath, Language dropdown)
    lang = "Auto" if not lang_code else lang_code  # "en" / "he" / "ar"
    result = client.predict(
        handle_file(str(wav_path)),
        lang,
        api_name="/predict",
    )
    # result is a dict from the Space JSON output
    return result


# =========================
# Streamlit UI
# =========================
st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title("🎙️ LiveCoach — Record → Transcribe (HF Space Backend)")
st.caption(
    "This version offloads transcription to your Hugging Face Space (soaad34/callcoach-transcribe). "
    "Your computer runs only the UI."
)

# Session state
ss = st.session_state
ss.setdefault("audio_bytes", None)
ss.setdefault("audio_hash", None)
ss.setdefault("last_transcript", "")
ss.setdefault("last_detected_lang", None)
ss.setdefault("last_lang_prob", None)
ss.setdefault("last_saved_path", None)
ss.setdefault("last_error", "")

# Controls
c1, c2, c3 = st.columns([1.2, 1.0, 1.3])

with c1:
    st.subheader("1) Record audio")
    st.write("Click to record, click again to stop. Keep it **short (≤ 10–15s)**.")

with c2:
    language_ui = st.selectbox(
        "Transcription language (optional)",
        ["Auto", "English (en)", "Hebrew (he)", "Arabic (ar)"],
        index=0,
    )
    lang_code = None
    if language_ui.startswith("English"):
        lang_code = "en"
    elif language_ui.startswith("Hebrew"):
        lang_code = "he"
    elif language_ui.startswith("Arabic"):
        lang_code = "ar"

with c3:
    # Keep it configurable (useful if you fork/change Spaces later)
    space_id = st.text_input("HF Space ID", value=SPACE_ID_DEFAULT, help="Format: username/space-name")

st.divider()

# Recorder widget -> returns WAV bytes (or None)
audio_bytes = audio_recorder(
    text="▶️ Start recording",
    recording_color="#e74c3c",
    neutral_color="#6aa36f",
    icon_name="microphone",
    icon_size="2x",
)

# Store new recording once
if audio_bytes:
    new_hash = sha1_bytes(audio_bytes)
    if ss.audio_hash != new_hash:
        ss.audio_bytes = audio_bytes
        ss.audio_hash = new_hash
        ss.last_error = ""

left, right = st.columns([1.1, 1.4])

with left:
    st.subheader("2) Save + Transcribe")

    if ss.audio_bytes:
        st.success(f"Audio captured ({len(ss.audio_bytes):,} bytes).")
        st.audio(ss.audio_bytes, format="audio/wav")

        if len(ss.audio_bytes) > MAX_AUDIO_BYTES:
            st.error(
                f"Recording is too large ({len(ss.audio_bytes):,} bytes). "
                f"Please record a shorter clip (aim for 5–15 seconds)."
            )
        else:
            with st.form("actions_form", clear_on_submit=False):
                colA, colB = st.columns([1.0, 1.3])
                save_clicked = colA.form_submit_button("💾 Save WAV")
                transcribe_clicked = colB.form_submit_button("🧠 Transcribe (HF Space)", type="primary")

            if save_clicked:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_path = SAVE_DIR / f"recording_{ts}.wav"
                write_wav_bytes(ss.audio_bytes, out_path)
                ss.last_saved_path = str(out_path)
                st.success(f"Saved: {out_path}")

            if transcribe_clicked:
                tmp_path = TMP_DIR / f"tmp_{ss.audio_hash}.wav"
                write_wav_bytes(ss.audio_bytes, tmp_path)

                try:
                    with st.spinner("Sending audio to HF Space and transcribing..."):
                        client = get_space_client(space_id.strip())
                        out = transcribe_via_space(client, tmp_path, lang_code)

                    ss.last_transcript = out.get("text", "") if isinstance(out, dict) else str(out)
                    ss.last_detected_lang = out.get("detected_language") if isinstance(out, dict) else None
                    ss.last_lang_prob = out.get("language_probability") if isinstance(out, dict) else None
                    st.success("Done!")

                except Exception as e:
                    ss.last_error = str(e)
                    st.error("Remote transcription failed. See error details below.")
                finally:
                    try:
                        tmp_path.unlink(missing_ok=True)
                    except Exception:
                        pass

    else:
        st.info("Record something to enable transcription.")

    if ss.last_saved_path:
        st.caption(f"Last saved file: `{ss.last_saved_path}`")

    if ss.last_error:
        st.code(ss.last_error, language="text")

with right:
    st.subheader("Transcript")

    if ss.last_transcript:
        st.text_area("Transcribed text", value=ss.last_transcript, height=240)

        if ss.last_detected_lang:
            prob_txt = ""
            if isinstance(ss.last_lang_prob, (float, int)):
                prob_txt = f" | Prob: {ss.last_lang_prob:.2f}"
            st.caption(f"Detected language: {ss.last_detected_lang}{prob_txt}")

        st.subheader("Simple analysis (starter)")
        t = ss.last_transcript.lower()

        frustration_markers = ["angry", "frustrated", "upset", "not happy", "annoyed", "disappointed"]
        confusion_markers = ["i don't understand", "what do you mean", "confused", "can you explain", "why"]

        fr = any(m in t for m in frustration_markers)
        cf = any(m in t for m in confusion_markers)

        if fr:
            st.warning("Potential negative sentiment detected → coaching type: Empathy/Acknowledge")
        if cf:
            st.warning("Potential confusion detected → coaching type: Clarify/Explain simply")
        if not (fr or cf):
            st.success("No obvious flags detected (basic rules).")

        st.caption("Next: trigger selective coaching cards only when needed.")
    else:
        st.info("Your transcript will appear here after transcription.")
