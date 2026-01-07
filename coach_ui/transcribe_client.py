import hashlib
from pathlib import Path
from typing import Any

from gradio_client import Client, handle_file

TMP_DIR = Path("tmp_audio")
TMP_DIR.mkdir(parents=True, exist_ok=True)

def sha1_bytes(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()

def write_wav_bytes(audio_bytes: bytes, out_path: Path) -> None:
    out_path.write_bytes(audio_bytes)

def transcribe_via_space(space_id: str, audio_bytes: bytes, lang_code: str | None) -> dict[str, Any]:
    tmp_path = TMP_DIR / f"chunk_{sha1_bytes(audio_bytes)}.wav"
    write_wav_bytes(audio_bytes, tmp_path)

    try:
        client = Client(space_id.strip())
        lang = "Auto" if not lang_code else lang_code

        out = client.predict(
            handle_file(str(tmp_path)),
            lang,
        )

        # Normalize output
        if isinstance(out, dict):
            return out
        return {"text": str(out)}
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
