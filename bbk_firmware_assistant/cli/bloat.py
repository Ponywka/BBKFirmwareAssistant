from __future__ import annotations

from pathlib import Path

from ..services import flasher
from ..services.bloat import BloatEntry, gunzip_to, load_catalog, sha256_file
from ..services.download import available_downloaders, build_command
from ._common import BLOAT_DIR, ask_confirm, ask_multiselect, ask_select, error, run_cmd, success
from .flash import Fastboot


def _fmt_size(n: int) -> str:
    for unit, div in (("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if n >= div:
            return f"{n / div:.1f} {unit}"
    return f"{n} B"


def _download_one(entry: BloatEntry, dest: Path, downloader: str) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    rc = run_cmd(*build_command(downloader, entry.url, tmp))
    if rc != 0:
        error(f"{entry.filename}: download failed (exit {rc})")
        return False
    if sha256_file(tmp) != entry.sha256:
        error(f"{entry.filename}: checksum mismatch (downloaded asset)")
        tmp.unlink(missing_ok=True)
        return False
    if entry.gzipped:
        gunzip_to(tmp, dest)
        tmp.unlink()
        if sha256_file(dest) != entry.raw_sha256:
            error(f"{entry.filename}: checksum mismatch (decompressed image)")
            dest.unlink()
            return False
    else:
        tmp.replace(dest)
    return True


def flow_bloat() -> None:
    entries = load_catalog()
    if not entries:
        error("Bloat catalog is empty. Regenerate data/bloat.json via tools/gen_bloat_json.py")
        return

    models = sorted({e.model for e in entries})
    model = ask_select("Model:", models)
    if not model:
        return

    scoped = sorted((e for e in entries if e.model == model),
                    key=lambda e: (e.region, e.filename))
    by_label: dict[str, BloatEntry] = {}
    choices = []
    for e in scoped:
        have = " ✓ have" if (BLOAT_DIR / e.model / e.region / e.filename).is_file() else ""
        label = f"{e.region}/{e.filename}  ({_fmt_size(e.raw_bytes)}){have}"
        by_label[label] = e
        choices.append(label)
    picked = ask_multiselect(f"Images to download ({model}):", choices)
    if not picked:
        return

    available = available_downloaders()
    if not available:
        error("No download tool found. Install wget, curl, or aria2c.")
        return
    downloader = ask_select("Download method:", available)
    if not downloader:
        return

    ok = 0
    for label in picked:
        e = by_label[label]
        dest = BLOAT_DIR / e.model / e.region / e.filename
        print(f"\n  {dest}  ({_fmt_size(e.bytes)} compressed)")
        if _download_one(e, dest, downloader):
            success(f"saved {dest}")
            ok += 1

    print()
    if ok == len(picked):
        success(f"All {ok} image(s) saved under {BLOAT_DIR}")
    else:
        error(f"{ok} of {len(picked)} image(s) saved")


def flow_bloat_flash() -> None:
    """Flash downloaded bloat images as logical (dynamic) partitions from fastbootd."""
    if not flasher.fastboot_available():
        error("fastboot not found in PATH")
        return

    BLOAT_DIR.mkdir(parents=True, exist_ok=True)
    models = sorted({p.relative_to(BLOAT_DIR).parts[0] for p in BLOAT_DIR.glob("*/*/*.img")})
    if not models:
        error(f"No bloat images found in {BLOAT_DIR}. Use 'Download bloat images' first.")
        return

    model = ask_select("Model:", models)
    if not model:
        return
    regions = sorted({p.relative_to(BLOAT_DIR).parts[1] for p in BLOAT_DIR.glob(f"{model}/*/*.img")})
    region = ask_select(f"Region ({model}):", regions)
    if not region:
        return

    img_dir = BLOAT_DIR / model / region
    files = sorted(img_dir.glob("*.img"))
    picked = ask_multiselect(f"Images to flash ({model}/{region}):", [f.name for f in files])
    if not picked:
        return
    selected = [img_dir / name for name in picked]

    unknown = [f.name for f in selected if f.stem.lower() not in flasher.DYNAMIC_PARTS]
    if unknown:
        print("\n  ⚠ Not known dynamic partitions: " + ", ".join(unknown))
        print("  They will still be recreated as logical partitions of size 0.")

    slot_mode = ask_select("Slots to flash:", list(flasher.BLOAT_SLOT_MODES))
    if not slot_mode:
        return
    slots = flasher.BLOAT_SLOT_MODES[slot_mode]

    mode = ask_select("Mode:", ["Dry-run (show commands only)", "Flash (write to device)"])
    if not mode:
        return
    dry = mode.startswith("Dry")

    if not dry:
        print("\n  ⚠ WARNING: This overwrites logical partitions with donor images.")
        if not ask_confirm("Proceed with flashing?"):
            print("  Cancelled.")
            return

    fb = Fastboot(dry)
    if dry:
        print("\n# dry-run — no commands will be executed\n")
    elif not ask_confirm("Device is in fastbootd (userspace fastboot) and connected?"):
        print("  Cancelled.")
        return

    if flasher.needs_device_slot(slots):
        current = fb.current_slot()
        if not current:
            return
        slots = flasher.resolve_slots(slots, current)

    for f in selected:
        for slot in slots:
            fb.run("delete-logical-partition", f"{f.stem}{slot}-cow")
            fb.run("delete-logical-partition", f"{f.stem}{slot}")
            fb.run("create-logical-partition", f"{f.stem}{slot}", "0")
    for f in selected:
        for slot in slots:
            if not fb.flash_or_retry("flash", f.stem + slot, str(f)):
                return

    if not dry:
        if ask_select("Did you see any errors?", ["No errors — continue", "Stop"]) == "Stop":
            print("  Stopped.")
            return
        if ask_select("Reboot to system?", ["Yes", "No"] ) == "Yes":
            fb.run("reboot")

    if dry:
        success("Dry-run complete — no changes were made.")
    else:
        success("Bloat flash complete!")
