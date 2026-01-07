import io
import time
import wave
from dataclasses import dataclass
from typing import Optional, Tuple, List

import streamlit as st

from coach_ui.style import inject_global_css
from coach_ui.state import init_state, go
from coach_ui.mock_data import waiting_calls, past_calls, live_script, post_call_summary
from coach_ui.transcribe_client import transcribe_via_space


# =========================
# Optional: continuous mic via streamlit-webrtc
# =========================
WEBRTC_AVAILABLE = True
try:
    import numpy as np
    from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
except Exception:
    WEBRTC_AVAILABLE = False


# =========================
# Page config
# =========================
st.set_page_config(page_title="LiveCoach", page_icon="🎧", layout="wide")

init_state()
inject_global_css()


# =========================
# Small helpers
# =========================
def sev_class(sev: str) -> str:
    sev = (sev or "").lower()
    if sev == "high":
        return "sev-high"
    if sev == "med":
        return "sev-med"
    return "sev-low"


def top_header():
    left, right = st.columns([1, 1])
    with left:
        st.markdown("## 🎧 LiveCoach")
        st.markdown(
            '<p class="muted" style="margin-top:-8px;">Real-time coaching for customer service calls</p>',
            unsafe_allow_html=True,
        )
    with right:
        if st.session_state.logged_in:
            st.markdown(
                f'<div style="display:flex; justify-content:flex-end; gap:10px;">'
                f'<div class="pill"><span class="dot" style="background:rgba(47,107,255,0.8); '
                f'box-shadow:0 0 0 4px rgba(47,107,255,0.12);"></span>'
                f'{st.session_state.login_email or "agent@company.com"}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
    st.write("")


def safe_reset_live_session():
    """Works even if you didn’t add reset_live_session() yet."""
    st.session_state.live_transcript = []
    st.session_state.live_idx = 0
    st.session_state.call_seconds = 0
    st.session_state.live_play = False
    st.session_state.live_started = False
    st.session_state.last_chunk_text = ""
    st.session_state.live_last_error = ""
    st.session_state.last_audio_hash = None
    st.session_state.live_listening = False
    st.session_state.transcribing = False
    st.session_state.transcribe_retries = 0
    st.session_state.warmup_done = False
    st.session_state.last_flush_ts = 0.0


# =========================
# Continuous audio buffering (WebRTC)
# =========================
CHUNK_SECONDS = 10  # feels continuous, keeps requests small => fewer HF timeouts
POLL_SECONDS = 0.6  # UI refresh cadence during live call


def _pcm_to_wav_bytes(pcm: "np.ndarray", sample_rate: int) -> bytes:
    """
    pcm: ndarray shape (n, ch) or (n,)
    streamlit-webrtc audio frames are typically int16 already; we handle floats too.
    """
    if pcm.ndim == 1:
        nch = 1
    else:
        nch = int(pcm.shape[1])

    if pcm.dtype != np.int16:
        # if float, assume [-1,1]
        pcm = np.clip(pcm, -1.0, 1.0)
        pcm = (pcm * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(nch)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


if WEBRTC_AVAILABLE:

    class BufferedAudioProcessor(AudioProcessorBase):
        """
        Continuously collects audio frames. Main thread periodically "flushes" them
        into a WAV chunk for remote transcription.
        """
        def __init__(self):
            self.frames: List["np.ndarray"] = []
            self.sample_rate: int = 48000  # fallback
            self.last_flush_ts: float = time.time()

        def recv_audio(self, frame):
            # frame: av.AudioFrame
            try:
                pcm = frame.to_ndarray()
                # Ensure shape (n, ch)
                if pcm.ndim == 1:
                    pcm = pcm[:, None]
                self.frames.append(pcm)
                # Best-effort sample rate
                if getattr(frame, "sample_rate", None):
                    self.sample_rate = int(frame.sample_rate)
            except Exception:
                pass
            return frame

        def pop_chunk_if_ready(self, chunk_seconds: float) -> Optional[Tuple[bytes, int]]:
            now = time.time()
            if (now - self.last_flush_ts) < chunk_seconds:
                return None
            if not self.frames:
                self.last_flush_ts = now
                return None

            try:
                pcm = np.concatenate(self.frames, axis=0)
            except Exception:
                self.frames = []
                self.last_flush_ts = now
                return None

            self.frames = []
            self.last_flush_ts = now
            wav_bytes = _pcm_to_wav_bytes(pcm, sample_rate=self.sample_rate)
            return wav_bytes, self.sample_rate


# =========================
# Components
# =========================
def render_transcript_panel(transcript, live_idx: int | None = None):
    st.markdown('<div class="glass soft">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Live transcript</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="muted" style="margin-top:-4px;">Shown for context. Coaching is the primary focus.</p>',
        unsafe_allow_html=True,
    )
    st.write("")

    if not transcript:
        st.markdown(
            "<div class='pill'><span class='dot'></span><span class='muted'>No transcript yet.</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if live_idx is None:
        start = max(0, len(transcript) - 8)
        end = len(transcript)
    else:
        start = max(0, live_idx - 7)
        end = min(len(transcript), live_idx + 1)

    for speaker, text in transcript[start:end]:
        st.markdown(
            f"""
            <div class="transcript-line">
              <div class="speaker">{speaker}</div>
              <div style="font-size:14px; opacity:0.9;">{text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def compute_rule_suggestions(transcript) -> dict:
    suggestions = {}
    if not transcript:
        return suggestions

    frustration_markers = ["angry", "frustrated", "upset", "not happy", "annoyed", "disappointed"]
    confusion_markers = ["i don't understand", "what do you mean", "confused", "can you explain", "why", "how"]

    window = transcript[-6:]
    flat_text = " ".join([t.lower() for _, t in window])

    idx = len(transcript) - 1

    if any(m in flat_text for m in frustration_markers):
        suggestions[idx] = (
            "Acknowledge emotion",
            "Use empathy: “I understand this is frustrating — I’m here to help.”",
            "high",
        )
    elif any(m in flat_text for m in confusion_markers):
        suggestions[idx] = (
            "Clarify simply",
            "Slow down + restate in one sentence, then ask: “Did I get that right?”",
            "med",
        )
    else:
        if idx % 4 == 0:
            suggestions[idx] = (
                "Confirm next step",
                "Summarize the agreed action and confirm timeline.",
                "low",
            )
    return suggestions


def render_coach_overlay(transcript, suggestions, live_idx: int | None = None):
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Coach guidance</div>', unsafe_allow_html=True)

    # Recording indicator
    rec_label = "Listening…" if st.session_state.get("live_listening") else "Ready"
    rec_dot = "rec-dot" if st.session_state.get("live_listening") else "dot"
    st.markdown(
        f"""
        <div class="rec" style="margin-bottom:12px;">
          <span class="{rec_dot}"></span>
          <div style="font-weight:900;">{rec_label}</div>
          <div class="muted" style="font-size:13px;">
            {("Call audio is being captured for coaching" if st.session_state.get("live_listening") else "Start the call to begin live coaching")}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    current_idx = (len(transcript) - 1) if (live_idx is None and transcript) else (live_idx or 0)

    active = []
    for k in sorted(suggestions.keys()):
        if k <= current_idx:
            active.append((k,) + suggestions[k])

    if not active:
        st.markdown(
            """
            <div class="coach-card coach-primary">
              <div style="display:flex; justify-content:space-between; align-items:center; gap:12px;">
                <h2 style="margin:0;">Listening…</h2>
                <span class="badge sev-low">READY</span>
              </div>
              <div style="height:10px;"></div>
              <p class="hint" style="font-size:16px;">
                Your next coaching tip will appear here the moment it’s needed.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    newest = active[-1]
    previous = active[-3:-1]

    _, title, hint, sev = newest
    st.markdown(
        f"""
        <div class="coach-primary">
          <div style="display:flex; justify-content:space-between; align-items:center; gap:12px;">
            <h2>{title}</h2>
            <span class="badge {sev_class(sev)}">{sev.upper()}</span>
          </div>
          <div style="height:10px;"></div>
          <p class="hint" style="font-size:17px; margin:0;">
            <b>Do now:</b> {hint}
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if previous:
        st.write("")
        st.markdown('<p class="muted" style="margin:2px 0 8px 0;">Recent guidance</p>', unsafe_allow_html=True)
        for (_, ptitle, phint, psev) in reversed(previous):
            st.markdown(
                f"""
                <div class="coach-card" style="padding:14px;">
                  <div style="display:flex; justify-content:space-between; align-items:center; gap:12px;">
                    <h3 style="margin:0; font-size:16px;">{ptitle}</h3>
                    <span class="badge {sev_class(psev)}">{psev.upper()}</span>
                  </div>
                  <div style="height:6px;"></div>
                  <p class="hint" style="font-size:14px;">{phint}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.write("")

    st.markdown("</div>", unsafe_allow_html=True)


def render_status_panel(call_id: str, line_no: int, call_seconds: int):
    mins = call_seconds // 60
    secs = call_seconds % 60
    t = f"{mins:02d}:{secs:02d}"

    st.markdown('<div class="glass soft">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Call status</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div style="display:flex; flex-direction:column; gap:10px;">
          <div class="pill">
            <span class="dot" style="background:rgba(34,197,94,0.85); box-shadow:0 0 0 4px rgba(34,197,94,0.12);"></span>
            Live · {call_id}
          </div>
          <div class="pill">
            <span class="dot" style="background:rgba(47,107,255,0.85); box-shadow:0 0 0 4px rgba(47,107,255,0.12);"></span>
            Timer · {t}
          </div>
          <div class="pill"><span class="dot"></span> Transcript line · {line_no}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")

    cols = st.columns([1, 1], gap="small")
    with cols[0]:
        if st.button("End call", use_container_width=True):
            st.session_state.last_call_id = call_id
            st.session_state.active_call_id = None
            st.session_state.post_call_sent = False
            safe_reset_live_session()
            go("post_call")

    with cols[1]:
        if st.button("Back to dashboard", use_container_width=True):
            go("dashboard")

    st.markdown("</div>", unsafe_allow_html=True)


# =========================
# Pages
# =========================
def page_login():
    top_header()
    left, right = st.columns([1.15, 0.85], gap="large")

    with left:
        st.markdown('<div class="glass">', unsafe_allow_html=True)
        st.markdown("### Sign in")
        st.markdown('<p class="muted">Use your work credentials to continue.</p>', unsafe_allow_html=True)
        st.write("")

        st.text_input("Work email", placeholder="name@company.com", key="login_email")
        st.text_input("Password", type="password", placeholder="••••••••", key="login_password")

        st.write("")
        disabled = not (st.session_state.login_email.strip() and st.session_state.login_password.strip())
        if st.button("Continue", use_container_width=True, disabled=disabled):
            st.session_state.logged_in = True
            st.session_state.page = "dashboard"
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown(
            """
            <div class="glass soft">
              <h3 style="margin:0 0 6px 0;">What you’ll see</h3>
              <p class="muted" style="margin:0;">
                A live call screen where real-time guidance is the primary focus,
                plus post-call analysis for learning and supervisor review.
              </p>
              <div style="height:12px;"></div>
              <div class="pill"><span class="dot" style="background:rgba(239,68,68,0.85);"></span> Recording indicator</div>
              <div style="height:10px;"></div>
              <div class="pill"><span class="dot" style="background:rgba(47,107,255,0.85);"></span> Center coaching cards</div>
              <div style="height:10px;"></div>
              <div class="pill"><span class="dot" style="background:rgba(34,197,94,0.85);"></span> Post-call summary</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def page_dashboard():
    top_header()
    left, right = st.columns([1.05, 0.95], gap="large")

    with left:
        st.markdown('<div class="glass">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Waiting calls</div>', unsafe_allow_html=True)
        st.write("")

        for c in waiting_calls():
            row = st.columns([0.9, 1.2, 0.7, 0.7], gap="small")
            row[0].markdown(f"**{c.customer}**")
            row[1].markdown(f"<span class='muted'>{c.topic}</span>", unsafe_allow_html=True)
            row[2].markdown(f"<span class='muted'>{c.wait_time}</span>", unsafe_allow_html=True)
            row[3].markdown(f"<span class='badge {sev_class(c.risk)}'>{c.risk.upper()}</span>", unsafe_allow_html=True)

            if st.button(f"Take call {c.call_id}", use_container_width=True):
                st.session_state.active_call_id = c.call_id
                st.session_state.page = "take_call"
                st.session_state.post_call_sent = False
                safe_reset_live_session()
                st.rerun()

            st.write("")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="glass soft">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Past calls</div>', unsafe_allow_html=True)
        st.write("")
        for p in past_calls():
            st.markdown(
                f"""
                <div class="pill" style="width:100%; justify-content:space-between;">
                  <div><b>{p.customer}</b> <span class="muted">· {p.topic}</span></div>
                  <div class="muted">{p.when} · <b>{p.grade}</b></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.write("")
        st.markdown("</div>", unsafe_allow_html=True)


def page_take_call():
    top_header()

    call_id = st.session_state.active_call_id or "W-0000"

    # Toggle between demo mode and real mode
    st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
    topbar = st.columns([1.2, 1.0, 1.0], gap="small")
    with topbar[0]:
        demo_mode = st.toggle("Demo mode (mock script)", value=False, help="Use scripted transcript & tips")
    with topbar[1]:
        lang_ui = st.selectbox("Language", ["Auto", "en", "he", "ar"], index=0)
        st.session_state.lang_code = None if lang_ui == "Auto" else lang_ui
    with topbar[2]:
        st.session_state.space_id = st.text_input(
            "HF Space ID",
            value=st.session_state.space_id,
            help="Format: username/space-name",
        )

    # Data sources
    if demo_mode:
        transcript, suggestions = live_script(call_id)
        live_idx = st.session_state.live_idx
        if not st.session_state.live_started:
            st.session_state.live_started = True
            st.session_state.live_play = True
            st.session_state.live_idx = 0
            st.session_state.call_seconds = 0
            live_idx = 0
    else:
        transcript = st.session_state.live_transcript
        suggestions = compute_rule_suggestions(transcript)
        live_idx = None

        if not st.session_state.live_started:
            st.session_state.live_started = True
            st.session_state.live_play = False
            st.session_state.call_seconds = 0
            st.session_state.live_listening = False
            st.session_state.transcribing = False
            st.session_state.transcribe_retries = 0
            st.session_state.warmup_done = False
            st.session_state.last_flush_ts = time.time()

    # Layout
    left, center, right = st.columns([0.85, 1.60, 0.70], gap="large")

    with left:
        render_transcript_panel(transcript, live_idx=live_idx)

    with center:
        # ---- Live capture block (REAL mode only) ----
        if not demo_mode:
            st.markdown('<div class="glass">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Live capture</div>', unsafe_allow_html=True)
            st.markdown(
                "<p class='muted' style='margin-top:-4px;'>Looks continuous. Under the hood we transcribe small batches automatically.</p>",
                unsafe_allow_html=True,
            )
            st.write("")

            # One user gesture is required by browsers to enable mic.
            cols = st.columns([1, 1], gap="small")
            with cols[0]:
                if not st.session_state.get("live_listening"):
                    if st.button("Start call (enable mic)", use_container_width=True, type="primary"):
                        st.session_state.live_listening = True
                        st.session_state.live_last_error = ""
                        st.session_state.transcribe_retries = 0
                        st.session_state.warmup_done = False
                        st.session_state.last_flush_ts = time.time()
                        st.rerun()
                else:
                    st.markdown(
                        "<div class='pill'><span class='dot' style='background:rgba(239,68,68,0.85);'></span>"
                        "<b>Listening</b> <span class='muted'>— capturing audio continuously</span></div>",
                        unsafe_allow_html=True,
                    )

            with cols[1]:
                speaker = st.radio("Speaker", ["Agent", "Customer"], horizontal=True, index=0)
                st.session_state.live_speaker = speaker

            st.write("")

            if not WEBRTC_AVAILABLE:
                st.warning(
                    "Continuous mic capture requires `streamlit-webrtc`. "
                    "Add it to requirements.txt (streamlit-webrtc, av, numpy) and redeploy."
                )
            else:
                # WebRTC mic (continuous capture)
                ctx = webrtc_streamer(
                    key="live_mic",
                    mode=WebRtcMode.SENDONLY,
                    audio_processor_factory=BufferedAudioProcessor,
                    media_stream_constraints={"audio": True, "video": False},
                    desired_playing=bool(st.session_state.get("live_listening")),
                )

                # Status line (non-scary)
                if st.session_state.get("transcribing"):
                    st.info("Transcribing… (this updates every ~10 seconds)")
                elif st.session_state.get("live_listening"):
                    st.success("Listening… transcript will update continuously.")
                else:
                    st.info("Click “Start call (enable mic)” to begin.")

                # Attempt to flush + transcribe periodically
                if st.session_state.get("live_listening") and ctx.audio_processor:
                    chunk = ctx.audio_processor.pop_chunk_if_ready(CHUNK_SECONDS)
                    if chunk and not st.session_state.get("transcribing"):
                        wav_bytes, _sr = chunk

                        # Avoid overlapping transcribes
                        st.session_state.transcribing = True
                        st.session_state.live_last_error = ""

                        try:
                            out = transcribe_via_space(
                                st.session_state.space_id,
                                wav_bytes,
                                st.session_state.lang_code,
                            )
                            text = (out.get("text", "") if isinstance(out, dict) else str(out)).strip()
                            st.session_state.last_chunk_text = text

                            if text:
                                spk = st.session_state.get("live_speaker", "Agent")
                                st.session_state.live_transcript.append((spk, text))

                            st.session_state.transcribe_retries = 0
                        except Exception as e:
                            # Keep the UX calm: show "delayed, retrying" instead of huge red blocks
                            st.session_state.transcribe_retries = int(st.session_state.get("transcribe_retries", 0)) + 1
                            st.session_state.live_last_error = str(e)

                            # If it keeps failing, we still keep listening; transcript will catch up later.
                            st.warning(f"Transcription delayed… retrying ({st.session_state.transcribe_retries}/3)")
                        finally:
                            st.session_state.transcribing = False

                # Compact error display (optional)
                if st.session_state.get("live_last_error"):
                    with st.expander("Details (debug)", expanded=False):
                        st.code(st.session_state.live_last_error, language="text")

            st.markdown("</div>", unsafe_allow_html=True)
            st.write("")

        # ---- Coach overlay (both modes) ----
        render_coach_overlay(transcript, suggestions, live_idx=st.session_state.live_idx if demo_mode else None)

        # ---- Demo controls (DEMO mode only) ----
        if demo_mode:
            st.write("")
            controls = st.columns([1, 1, 1], gap="small")
            with controls[0]:
                if st.button("Pause", use_container_width=True):
                    st.session_state.live_play = False
                    st.rerun()
            with controls[1]:
                if st.button("Resume", use_container_width=True):
                    st.session_state.live_play = True
                    st.rerun()
            with controls[2]:
                if st.button("Skip +1", use_container_width=True):
                    st.session_state.live_idx = min(st.session_state.live_idx + 1, len(transcript) - 1)
                    st.rerun()

    with right:
        line_no = (st.session_state.live_idx + 1) if demo_mode else (len(transcript))
        render_status_panel(call_id, line_no, st.session_state.call_seconds)

    # Auto-advance (demo) or keep polling (real)
    if demo_mode and st.session_state.live_play:
        time.sleep(0.6)
        st.session_state.call_seconds += 1
        if st.session_state.live_idx < len(transcript) - 1:
            st.session_state.live_idx += 1
        st.rerun()

    if (not demo_mode) and st.session_state.get("live_listening"):
        # Poll UI to feel "live" + increment timer
        time.sleep(POLL_SECONDS)
        st.session_state.call_seconds += int(POLL_SECONDS)
        st.rerun()


def page_post_call():
    top_header()
    call_id = st.session_state.last_call_id or "W-0000"
    summary = post_call_summary(call_id)

    left, right = st.columns([1.25, 0.75], gap="large")

    with left:
        st.markdown('<div class="glass">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Post-call analysis</div>', unsafe_allow_html=True)
        st.markdown(f"### Call {summary['call_id']}")
        st.markdown(f"<p class='muted'>{summary['overall']}</p>", unsafe_allow_html=True)

        st.write("")
        st.markdown("#### What went well")
        for x in summary["highlights"]:
            st.markdown(f"- {x}")

        st.write("")
        st.markdown("#### What to improve next time")
        for x in summary["improvements"]:
            st.markdown(f"- {x}")

        st.write("")
        btns = st.columns([1, 1, 1], gap="small")
        with btns[0]:
            if st.button("Send to supervisor", use_container_width=True):
                st.session_state.post_call_sent = True
                st.toast("Sent to supervisor ✓", icon="✅")
                st.rerun()
        with btns[1]:
            if st.button("Back to dashboard", use_container_width=True):
                go("dashboard")
        with btns[2]:
            if st.button("Take next call", use_container_width=True):
                go("dashboard")

        if st.session_state.post_call_sent:
            st.markdown(
                "<div class='pill' style='margin-top:10px;'><span class='dot' style='background:rgba(34,197,94,0.85);'></span>"
                "<b>Supervisor report sent</b> <span class='muted'>— available in QA dashboard</span></div>",
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="glass soft">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Quality signals</div>', unsafe_allow_html=True)

        m = summary["metrics"]
        st.markdown(
            f"""
            <div class="metric-grid">
              <div class="metric-tile"><div class="metric-label">Empathy</div><div class="metric-val">{m['Empathy']:.1f}/5</div></div>
              <div class="metric-tile"><div class="metric-label">Clarity</div><div class="metric-val">{m['Clarity']:.1f}/5</div></div>
              <div class="metric-tile"><div class="metric-label">Control</div><div class="metric-val">{m['Control']:.1f}/5</div></div>
              <div class="metric-tile"><div class="metric-label">Professionalism</div><div class="metric-val">{m['Professionalism']:.1f}/5</div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.write("")
        st.markdown('<div class="section-title">Supervisor note</div>', unsafe_allow_html=True)
        st.markdown(f"<p class='muted'>{summary['supervisor_note']}</p>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)


# =========================
# Router
# =========================
if not st.session_state.logged_in:
    st.session_state.page = "login"

if st.session_state.page == "login":
    page_login()
elif st.session_state.page == "dashboard":
    page_dashboard()
elif st.session_state.page == "take_call":
    page_take_call()
elif st.session_state.page == "post_call":
    page_post_call()
else:
    page_dashboard()
