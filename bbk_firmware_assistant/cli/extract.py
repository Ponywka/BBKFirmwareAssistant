from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from ..services.extractor import find_dumper, read_ota_metadata
from ._common import DOWNLOADS_DIR, EXTRACTED_DIR, ask_confirm, ask_path, ask_select, error, run_cmd, success

CHUNK_SIZE = 4 * 1024 * 1024


def _select_ota_file() -> Path | None:
    """Let the user pick an OTA file from the downloads dir or type a path."""
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(
        p for p in DOWNLOADS_DIR.iterdir()
        if p.suffix.lower() in (".zip", ".bin")
    )

    MANUAL = "[ Enter path manually ]"
    picked = ask_select(f"Select OTA file (in {DOWNLOADS_DIR}):", [str(f) for f in files] + [MANUAL])
    if not picked:
        return None
    if picked == MANUAL:
        picked = ask_path("Path to .zip or payload.bin:")
        if not picked:
            return None

    ota_path = Path(picked)
    if not ota_path.exists():
        error(f"File not found: {ota_path}")
        return None
    return ota_path


def _extract_payload(zip_path: Path, out_dir: Path) -> Path | None:
    """Extract payload.bin from an OTA ZIP into out_dir. Returns its path, or None on error."""
    print("  Extracting payload.bin from ZIP...")
    out_dir.mkdir(parents=True, exist_ok=True)
    payload_path = out_dir / "payload.bin"
    try:
        with zipfile.ZipFile(zip_path) as zf:
            bin_name = next((n for n in zf.namelist() if n.endswith("payload.bin")), None)
            if not bin_name:
                error("payload.bin not found in ZIP")
                return None
            with zf.open(bin_name) as src, open(payload_path, "wb") as dst:
                shutil.copyfileobj(src, dst, CHUNK_SIZE)
        success("payload.bin extracted")
        return payload_path
    except Exception as e:
        error(f"ZIP extraction failed: {e}")
        return None


def flow_extract() -> None:
    ota_path = _select_ota_file()
    if not ota_path:
        return

    is_zip = ota_path.suffix.lower() == ".zip"
    dir_name = ota_path.stem
    if is_zip:
        dir_name = read_ota_metadata(ota_path).get("version_name") or dir_name
    out_dir = EXTRACTED_DIR / dir_name
    print(f"\n  Output directory: {out_dir}")

    dumper = find_dumper()
    if not dumper:
        error(
            "payload-dumper-go not found in PATH.\n"
            "  Install it from https://github.com/ssut/payload-dumper-go/releases"
        )
        return

    if is_zip:
        payload_path = _extract_payload(ota_path, out_dir)
        if not payload_path:
            return
    else:
        payload_path = ota_path

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n  Running {dumper}...\n")
    rc = run_cmd(dumper, "-o", str(out_dir), str(payload_path))
    if rc != 0:
        error(f"payload-dumper-go exited with code {rc}")
        return

    imgs = sorted(p.name for p in out_dir.glob("*.img"))
    success(f"Extracted {len(imgs)} partition images to {out_dir}")
    if imgs:
        print("  " + ", ".join(imgs[:8]) + ("..." if len(imgs) > 8 else ""))

    # payload.bin is no longer needed once the images are out (it's ~as large as all of them)
    if payload_path.is_file() and payload_path.parent == out_dir:
        size_gb = payload_path.stat().st_size / 1024**3
        if ask_confirm(f"Delete {payload_path.name} (freed {size_gb:.1f} GB)?"):
            payload_path.unlink()
            print(f"  Deleted {payload_path.name}")

    success("Done — ready to flash")