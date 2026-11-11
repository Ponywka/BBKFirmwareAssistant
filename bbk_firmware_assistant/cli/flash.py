from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..services import flasher
from ._common import EXTRACTED_DIR, ask_confirm, ask_path, ask_select, error, success

MANUAL_PATH = "[ Enter path manually ]"


class Fastboot:
    """Thin fastboot wrapper. In dry-run mode it only prints commands."""

    def __init__(self, dry_run: bool) -> None:
        self.dry_run = dry_run

    def run(self, *args: str) -> int:
        if self.dry_run:
            print(f"fastboot {' '.join(args)}")
            return 0
        print(f"  $ fastboot {' '.join(args)}")
        return subprocess.run(["fastboot", *args]).returncode

    def current_slot(self) -> str | None:
        """Return "_a"/"_b" from the device (asks the user in dry-run), or None if unknown."""
        if self.dry_run:
            pick = ask_select("Current slot on the device (needed for the dry-run):", ["a", "b"])
            return f"_{pick}" if pick else None
        res = subprocess.run(["fastboot", "getvar", "current-slot"],
                             capture_output=True, text=True)
        m = re.search(r"current-slot:\s*_?([ab])\b", res.stdout + res.stderr)
        if not m:
            error("Could not read current-slot from the device")
            return None
        print(f"  Device current slot: {m.group(1)}")
        return f"_{m.group(1)}"

    def flash_or_retry(self, *args: str) -> bool:
        """Run a fastboot command; on failure ask the user to retry or stop."""
        while True:
            if self.run(*args) == 0:
                return True
            choice = ask_select(
                f"fastboot {' '.join(args[:2])} failed — retry or stop?",
                ["Retry", "Stop"],
            )
            if choice != "Retry":
                return False


def _select_firmware_dir() -> Path | None:
    """Let the user pick a firmware dir with .img files, or type a path."""
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    dirs = sorted(d for d in EXTRACTED_DIR.iterdir() if d.is_dir())

    def summary(d: Path) -> str:
        n = len(list(d.glob("*.img"))) + len(list(d.glob("*/*.img")))
        return f"{d.name}  ({n} image{'s' if n != 1 else ''})"

    choices = [summary(d) for d in dirs] + [MANUAL_PATH]
    picked = ask_select(f"Select firmware (in {EXTRACTED_DIR}):", choices)
    if not picked:
        return None

    if picked == MANUAL_PATH:
        path = ask_path("Path to directory with .img files:")
        img_dir = Path(path) if path else None
    else:
        img_dir = dirs[choices.index(picked)]

    if not img_dir or not img_dir.is_dir():
        if img_dir:
            error(f"Not a directory: {img_dir}")
        return None
    return img_dir


def flow_flash() -> None:
    if not flasher.fastboot_available():
        error("fastboot not found in PATH")
        return

    img_dir = _select_firmware_dir()
    if not img_dir:
        return

    images = flasher.collect_images(img_dir)
    skipped = sorted(
        f for f in [*img_dir.glob("*.img"), *img_dir.glob("*/*.img")]
        if flasher.never_flash(f.stem)
    )
    if skipped:
        print("\n  Skipping (never flashed): " + ", ".join(f.name for f in skipped))
    if not images:
        error(f"No .img files found in {img_dir}")
        return

    groups: dict[str, list[Path]] = {"bootloader": [], "super": [], "dynamic": [], "critical": []}
    for f in images:
        groups[flasher.classify(f)].append(f)

    print()
    for label in ("bootloader", "super", "dynamic", "critical"):
        shown = ", ".join(f.name for f in groups[label][:5])
        print(f"  {label}: {shown}{'...' if len(groups[label]) > 5 else ''}")

    slot_mode = ask_select("Slots to flash:", list(flasher.FIRMWARE_SLOT_MODES))
    if not slot_mode:
        return
    slots, dyn_slots = flasher.FIRMWARE_SLOT_MODES[slot_mode]

    mode = ask_select("Mode:", ["Dry-run (show commands only)", "Flash (write to device)"])
    if not mode:
        return
    dry = mode.startswith("Dry")

    android_ver = ask_select("Android version on device:", ["13-15", "12", "10-11"])
    if not android_ver:
        return

    if not dry:
        print("\n  ⚠ WARNING: This will flash your device.")
        if not ask_confirm("Proceed with flashing?"):
            print("  Cancelled.")
            return

    _do_flash(img_dir, groups, dry_run=dry, android_ver=android_ver,
              slots=slots, dyn_slots=dyn_slots)


def _flash_slots(fb: Fastboot, files: list[Path], slots: tuple[str, ...]) -> bool:
    """Flash each file to the given slots. Returns False if the user aborted."""
    for f in files:
        for slot in slots:
            if not fb.flash_or_retry("flash", f.stem + slot, str(f)):
                return False
    return True


def _header(text: str, dry_run: bool) -> None:
    """Print a section header: as a shell comment in dry-run, decorated otherwise."""
    print(f"\n# {text}" if dry_run else f"\n── {text} ──")


def _do_flash(
    img_dir: Path,
    groups: dict[str, list[Path]],
    dry_run: bool = False,
    android_ver: str = "13-15",
    slots: tuple[str, ...] = ("_a", "_b"),
    dyn_slots: tuple[str, ...] = ("_a", "_b"),
) -> None:
    fb = Fastboot(dry_run)

    if dry_run:
        print("\n# dry-run — no commands will be executed\n")
    else:
        print("\n── Step 1: Enter fastboot (bootloader mode) ──")
        print("  Power off the device, then hold  Volume Down + Power  until")
        print("  the Fastboot screen appears, connect USB.")
        print("  The device must show  Fastboot Mode  (NOT userspace/fastbootd).")
        if not ask_confirm("Device is in fastboot (bootloader) mode and connected?"):
            print("  Cancelled.")
            return

    if flasher.needs_device_slot(slots, dyn_slots):
        current = fb.current_slot()
        if not current:
            return
        slots = flasher.resolve_slots(slots, current)
        dyn_slots = flasher.resolve_slots(dyn_slots, current)

    # Phase 1 (bootloader-mode fastboot): boot/dtbo/vbmeta*/... plus modem, both slots.
    if groups.get("bootloader"):
        _header("BOOTLOADER partitions", dry_run)
        if not _flash_slots(fb, groups["bootloader"], slots):
            return

    _header("Rebooting into fastbootd", dry_run)
    fb.run("reboot", "fastboot")
    if not dry_run:
        if not ask_confirm("Device is in fastbootd (userspace fastboot) and connected?"):
            print("  Cancelled.")
            return

    if android_ver == "10-11":
        _header("Android 10-11 cleanup", dry_run)
        fb.run("delete-logical-partition", "my_bigball-cow")
        fb.run("delete-logical-partition", "my_bigball")

    skip_dynamic = False
    super_files = groups.get("super", [])
    if super_files:
        _header("SUPER", dry_run)
        if not fb.flash_or_retry("flash", "super", str(super_files[0])):
            return
        skip_dynamic = True  # super.img already contains the dynamic partitions

    critical = groups.get("critical", [])
    if critical:
        _header("CRITICAL", dry_run)
        if not _flash_slots(fb, critical, slots):
            return

    dynamic = groups.get("dynamic", [])
    if dynamic and not skip_dynamic:
        _header("SYSTEM (logical partitions)", dry_run)
        for f in dynamic:
            for slot in slots:
                fb.run("delete-logical-partition", f"{f.stem}{slot}-cow")
                fb.run("delete-logical-partition", f"{f.stem}{slot}")
                fb.run("create-logical-partition", f"{f.stem}{slot}", "0")
        for f in dynamic:
            for slot in dyn_slots:
                if not fb.flash_or_retry("flash", f.stem + slot, str(f)):
                    return

    if not dry_run:
        if ask_select("Did you see any errors?", ["No errors — continue", "Stop"]) == "Stop":
            print("  Stopped.")
            return
        slot = ask_select(
            "Set active slot? (conversion guides usually switch to A)",
            ["Don't change", "a", "b"] if dyn_slots != ("_b",) else ["Don't change", "b", "a"],
        )
        if slot in ("a", "b"):
            fb.run(f"--set-active={slot}")

    _header("Rebooting", dry_run)
    if dry_run:
        fb.run("reboot")
        success("Dry-run complete — no changes were made.")
        return

    action = ask_select(
        "Post-flash action:",
        ["Reboot to system", "Wipe data and reboot", "Do not reboot"],
    )
    if action == "Wipe data and reboot":
        fb.flash_or_retry("erase", "userdata")
        fb.run("reboot")
    elif action == "Reboot to system":
        fb.run("reboot")
    success("Flash complete!")
