"""OTA extraction service."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

def read_ota_metadata(zip_path: Path) -> dict[str, str]:
    """Read META-INF/com/android/metadata from an OTA ZIP. Returns key→value dict."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            meta_name = next(
                (n for n in zf.namelist() if n.endswith("META-INF/com/android/metadata")),
                None,
            )
            if not meta_name:
                return {}
            text = zf.read(meta_name).decode(errors="replace")
        result: dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
        return result
    except Exception:
        return {}


def find_dumper() -> str | None:
    for c in ("payload-dumper-go", "payload_dumper_go", "./payload-dumper-go"):
        if shutil.which(c):
            return c
    return None
