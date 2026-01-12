# import io
# import time
# import wave
# from pathlib import Path
# from typing import Optional, Tuple, List
#
# import streamlit as st
# from coach_ui.transcribe_client import transcribe_via_space
#
# WEBRTC_AVAILABLE = True
# try:
#     import numpy as np
#     from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
# except Exception:
#     WEBRTC_AVAILABLE = False
#
# APP_TITLE = "Debug: Continuous Listen + Save Full Call"
# SPACE_ID_DEFAULT = "soaad34/callcoach-transcribe"
#
# RECORDINGS_DIR = Path("recordings")
# RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
#
# CHUNK_SECONDS = 6.0
# POLL_SECONDS = 0.5
#
#
# def pcm_to_wav_bytes(pcm: "np.ndarray", sample_rate: int) -> bytes:
#     if pcm.ndim == 1:
#         nch = 1
#     else:
#         nch = int(pcm.shape[1])
#
#     if pcm.dtype != np.int16:
#         pcm = np.clip(pcm, -1.0, 1.0)
#         pcm = (pcm * 32767).astype(np.int16)
#
#     buf = io.BytesIO()
#     with wave.open(buf, "wb") as wf:
#         wf.setnchannels(nch)
#         wf.setsampwidth(2)
#         wf.setframerate(sample_rate)
#         wf.writeframes(pcm.tobytes())
#     return buf.getvalue()
#
#
# def write_wav_file(path: Path, pcm: "np.ndarray", sample_rate: int) -> None:
#     path.write_bytes(pcm_to_wav_bytes(pcm, sample_rate))
#
#
# if WEBRTC_AVAILABLE:
#
#     class DebugAudioProcessor(AudioProcessorBase):
#         """
#         Collects audio frames continuously.
#         - frames: for chunk-based flushing
#         - all_frames: for "save full call"
#         """
#         def __init__(self):
#             self.frames: List["np.ndarray"] = []
#             self.all_frames: List["np.ndarray"] = []
#             self.sample_rate: int = 48000
#             self.last_flush_ts: float = time.time()
#
#         def recv_audio(self, frame):
#             try:
#                 pcm = frame.to_ndarray()
#                 if pcm.ndim == 1:
#                     pcm = pcm[:, None]
#
#                 self.frames.append(pcm)
#                 self.all_frames.append(pcm)
#
#                 if getattr(frame, "sample_rate", None):
#                     self.sample_rate = int(frame.sample_rate)
#             except Exception:
#                 pass
#             return frame
#
#         def pop_chunk_if_ready(self, chunk_seconds: float) -> Optional[Tuple[bytes, int, int]]:
#             now = time.time()
#             if (now - self.last_flush_ts) < chunk_seconds:
#                 return None
#
#             if not self.frames:
#                 self.last_flush_ts = now
#                 return None
#
#             try:
#                 pcm = np.concatenate(self.frames, axis=0)
#             except Exception:
#                 self.frames = []
#                 self.last_flush_ts = now
#                 return None
#
#             self.frames = []
#             self.last_flush_ts = now
#
#             wav_bytes = pcm_to_wav_bytes(pcm, self.sample_rate)
#             n_samples = int(pcm.shape[0])
#             return wav_bytes, self.sample_rate, n_samples
#
#         def get_full_pcm(self) -> Optional[Tuple["np.ndarray", int]]:
#             if not self.all_frames:
#                 return None
#             try:
#                 pcm = np.concatenate(self.all_frames, axis=0)
#             except Exception:
#                 return None
#             return pcm, self.sample_rate
#
#
# # -------------------------
# # Streamlit UI
# # -------------------------
# st.set_page_config(page_title=APP_TITLE, layout="wide")
# st.title("🧪 Debug Recorder — Continuous vs Save-Full-Call")
# st.caption("Goal: pinpoint whether the issue is WebRTC capture, chunk flushing, or HF transcription.")
#
# ss = st.session_state
# ss.setdefault("space_id", SPACE_ID_DEFAULT)
# ss.setdefault("lang_code", None)
#
# ss.setdefault("listening", False)
# ss.setdefault("stop_requested", False)   # ✅ NEW: two-phase stop
# ss.setdefault("transcribing", False)
#
# ss.setdefault("mode", "Save full call (best debug)")
# ss.setdefault("live_lines", [])
# ss.setdefault("last_chunk_text", "")
# ss.setdefault("last_error", "")
# ss.setdefault("call_seconds", 0)
#
# ss.setdefault("saved_path", "")
# ss.setdefault("saved_bytes", 0)
# ss.setdefault("captured_samples", 0)
# ss.setdefault("captured_sr", 0)
# ss.setdefault("chunk_samples_last", 0)
# ss.setdefault("chunk_bytes_last", 0)
#
#
# def reset_state():
#     ss.listening = False
#     ss.stop_requested = False
#     ss.transcribing = False
#     ss.live_lines = []
#     ss.last_chunk_text = ""
#     ss.last_error = ""
#     ss.call_seconds = 0
#     ss.saved_path = ""
#     ss.saved_bytes = 0
#     ss.captured_samples = 0
#     ss.captured_sr = 0
#     ss.chunk_samples_last = 0
#     ss.chunk_bytes_last = 0
#
#
# top = st.columns([1.4, 0.8, 0.8, 0.6])
# with top[0]:
#     ss.space_id = st.text_input("HF Space ID", value=ss.space_id)
#
# with top[1]:
#     lang_ui = st.selectbox("Language", ["Auto", "en", "he", "ar"], index=0)
#     ss.lang_code = None if lang_ui == "Auto" else lang_ui
#
# with top[2]:
#     ss.mode = st.selectbox(
#         "Mode",
#         ["Save full call (best debug)", "Continuous chunks (debug)"],
#         index=0,
#     )
#
# with top[3]:
#     if st.button("Reset", use_container_width=True):
#         reset_state()
#         st.rerun()
#
# st.divider()
#
# left, right = st.columns([1.2, 1.0], gap="large")
#
# with left:
#     st.subheader("Transcript output")
#     if ss.live_lines:
#         st.text_area("Transcript", value="\n".join(ss.live_lines[-300:]), height=320)
#     else:
#         st.info("No transcript yet.")
#
#     if ss.saved_path and Path(ss.saved_path).exists():
#         st.success(f"Saved WAV: {ss.saved_path} ({ss.saved_bytes/1024:.1f} KB)")
#
#     if ss.last_chunk_text:
#         st.success(f"Last chunk text: {ss.last_chunk_text}")
#
#     if ss.last_error:
#         st.error("Last error:")
#         st.code(ss.last_error, language="text")
#
# with right:
#     st.subheader("Status / Debug signals")
#     mins = ss.call_seconds // 60
#     secs = ss.call_seconds % 60
#
#     st.markdown(f"**Listening:** {'✅' if ss.listening else '—'}")
#     st.markdown(f"**Stop requested:** {'✅' if ss.stop_requested else '—'}")
#     st.markdown(f"**Transcribing:** {'✅' if ss.transcribing else '—'}")
#     st.markdown(f"**Timer:** {mins:02d}:{secs:02d}")
#
#     if ss.captured_sr and ss.captured_samples:
#         approx_secs = ss.captured_samples / ss.captured_sr
#         st.markdown(f"**Captured audio:** ~{approx_secs:.1f}s @ {ss.captured_sr} Hz")
#     else:
#         st.markdown("**Captured audio:** —")
#
#     if ss.chunk_bytes_last:
#         st.markdown(f"**Last chunk:** {ss.chunk_bytes_last/1024:.1f} KB, {ss.chunk_samples_last} samples")
#
#     if not WEBRTC_AVAILABLE:
#         st.warning("streamlit-webrtc not available. Install: streamlit-webrtc, av, numpy.")
#
#
# # -------------------------
# # Controls
# # -------------------------
# c1, c2 = st.columns([1, 1])
# with c1:
#     if not ss.listening:
#         if st.button("▶️ Start listening (enable mic)", type="primary", use_container_width=True):
#             ss.listening = True
#             ss.stop_requested = False
#             ss.transcribing = False
#             ss.last_error = ""
#             ss.call_seconds = 0
#             ss.saved_path = ""
#             ss.saved_bytes = 0
#             ss.captured_samples = 0
#             ss.captured_sr = 0
#             ss.chunk_bytes_last = 0
#             ss.chunk_samples_last = 0
#             st.rerun()
#     else:
#         # ✅ NEW: don't kill listening immediately; request stop first
#         if st.button("⏹ Stop listening (save first)", use_container_width=True):
#             ss.stop_requested = True
#             st.rerun()
#
# with c2:
#     # ✅ NEW: enable based on actual file existence
#     can_transcribe = bool(ss.saved_path) and Path(ss.saved_path).exists()
#     if st.button("🧾 Transcribe saved WAV now", use_container_width=True, disabled=not can_transcribe):
#         try:
#             ss.transcribing = True
#             wav_bytes = Path(ss.saved_path).read_bytes()
#             out = transcribe_via_space(ss.space_id, wav_bytes, ss.lang_code)
#             text = (out.get("text", "") if isinstance(out, dict) else str(out)).strip()
#             if text:
#                 ss.live_lines.append(text)
#             ss.last_error = ""
#         except Exception as e:
#             ss.last_error = str(e)
#         finally:
#             ss.transcribing = False
#         st.rerun()
#
#
# # -------------------------
# # Capture loop
# # -------------------------
# if ss.listening and WEBRTC_AVAILABLE:
#     ctx = webrtc_streamer(
#         key="debug_mic",
#         mode=WebRtcMode.SENDONLY,
#         audio_processor_factory=DebugAudioProcessor,
#         media_stream_constraints={"audio": True, "video": False},
#     )
#
#     # If processor exists, we are receiving frames
#     if ctx.audio_processor:
#         # Update capture stats
#         full = ctx.audio_processor.get_full_pcm()
#         if full:
#             pcm, sr = full
#             ss.captured_samples = int(pcm.shape[0])
#             ss.captured_sr = int(sr)
#
#         # ✅ NEW: finalize/save on stop request (while ctx/audio_processor still alive)
#         if ss.stop_requested:
#             full = ctx.audio_processor.get_full_pcm()
#             if full:
#                 pcm, sr = full
#                 out_path = RECORDINGS_DIR / f"call_{int(time.time())}.wav"
#                 try:
#                     write_wav_file(out_path, pcm, sr)
#                     ss.saved_path = str(out_path)
#                     ss.saved_bytes = out_path.stat().st_size
#                     ss.last_error = ""
#                 except Exception as e:
#                     ss.last_error = f"Saving WAV failed: {e}"
#             else:
#                 ss.last_error = "Stop requested but no audio frames were captured (PCM empty)."
#
#             # now stop
#             ss.stop_requested = False
#             ss.listening = False
#             ss.transcribing = False
#             st.rerun()
#
#         # Mode A: Save full call (keep updating a preview file while listening)
#         if ss.mode == "Save full call (best debug)":
#             full = ctx.audio_processor.get_full_pcm()
#             if full:
#                 pcm, sr = full
#                 tmp_path = RECORDINGS_DIR / "latest_call.wav"
#                 try:
#                     write_wav_file(tmp_path, pcm, sr)
#                     ss.saved_path = str(tmp_path)
#                     ss.saved_bytes = tmp_path.stat().st_size
#                 except Exception as e:
#                     ss.last_error = f"Saving WAV failed: {e}"
#
#         # Mode B: chunk-based transcribe while listening
#         else:
#             chunk = ctx.audio_processor.pop_chunk_if_ready(CHUNK_SECONDS)
#             if chunk and not ss.transcribing:
#                 wav_bytes, _sr, n_samples = chunk
#                 ss.chunk_bytes_last = len(wav_bytes)
#                 ss.chunk_samples_last = n_samples
#
#                 try:
#                     ss.transcribing = True
#                     out = transcribe_via_space(ss.space_id, wav_bytes, ss.lang_code)
#                     text = (out.get("text", "") if isinstance(out, dict) else str(out)).strip()
#                     ss.last_chunk_text = text
#                     if text:
#                         ss.live_lines.append(text)
#                     ss.last_error = ""
#                 except Exception as e:
#                     ss.last_error = str(e)
#                 finally:
#                     ss.transcribing = False
#
#     # Poll UI ONLY while actively listening
#     time.sleep(POLL_SECONDS)
#     ss.call_seconds += 1
#     st.rerun()
#
# elif ss.listening and not WEBRTC_AVAILABLE:
#     st.warning("streamlit-webrtc missing, cannot capture continuous mic.")
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
MAX_AUDIO_BYTES = 200_000_000  # ~3MB


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


from gradio_client import Client, handle_file

def transcribe_via_space(client: Client, wav_path, lang_code: str | None) -> dict:
    lang = "Auto" if not lang_code else lang_code  # keep your mapping for now

    # Submit job (more robust than predict for long/waking Spaces)
    job = client.submit(
        handle_file(str(wav_path)),
        lang,
        # api_name="/predict"  # might need to change; see section below
    )
    # Wait longer for Space cold-start
    return job.result(timeout=180)


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