"""Fastboot flash service — name-based partition classification for flat firmware dirs."""

from __future__ import annotations

import shutil
from pathlib import Path

# Partitions flashed from bootloader-mode fastboot, to both _a and _b slots.
BOOTLOADER_PARTS: tuple[str, ...] = (
    "boot",
    "dtbo",
    "init_boot",
    "modem",
    "recovery",
    "vbmeta",
    "vbmeta_system",
    "vbmeta_vendor",
    "vendor_boot",
)

# Dynamic (logical) partitions recreated in fastbootd before flashing.
DYNAMIC_PARTS: tuple[str, ...] = (
    "my_bigball",
    "my_carrier",
    "my_company",
    "my_engineering",
    "my_heytap",
    "my_manifest",
    "my_preload",
    "my_product",
    "my_region",
    "my_stock",
    "odm",
    "odm_dlkm",
    "product",
    "system",
    "system_dlkm",
    "system_dlkm_gki",
    "system_dlkm_oki",
    "system_ext",
    "vendor",
    "vendor_dlkm",
)

SUPER_PARTS: tuple[str, ...] = ("super",)


def fastboot_available() -> bool:
    return bool(shutil.which("fastboot"))


def never_flash(name: str) -> bool:
    """True for images that must never be written to a device (preloader bricks MTK units)."""
    return name.startswith("preloader")


def classify(img: Path) -> str:
    """Classify an image by its file name (not by folder).

    Returns one of: "bootloader", "dynamic", "super", "critical".
    Anything unknown is treated as a physical partition flashed from fastbootd.
    """
    stem = img.stem.lower()
    if stem in SUPER_PARTS:
        return "super"
    if stem in BOOTLOADER_PARTS:
        return "bootloader"
    if stem in DYNAMIC_PARTS:
        return "dynamic"
    return "critical"


def collect_images(img_dir: Path) -> list[Path]:
    """Return flashable .img files from a firmware dir, skipping never-flash ones.

    Looks at the top level and one level of subdirs, so both flat dirs and
    legacy group dirs (BOOTLOADER/CRITICAL/SYSTEM/MODEM) work.
    """
    images = sorted(img_dir.glob("*.img")) + sorted(img_dir.glob("*/*.img"))
    return [f for f in images if not never_flash(f.stem)]


# Slot selection menus: label -> (slots for boot/critical partitions, slots for dynamic
# partitions such as system/vendor/product).
FIRMWARE_SLOT_MODES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "Flash only A slot": (("_a",), ("_a",)),
    "Flash only B slot": (("_b",), ("_b",)),
    "Flash both (super only A)": (("_a", "_b"), ("_a",)),
    "Flash both (super only B)": (("_a", "_b"), ("_b",)),
}

BLOAT_SLOT_MODES: dict[str, tuple[str, ...]] = {
    "Flash only A slot": ("_a",),
    "Flash only B slot": ("_b",),
    "Flash both": ("_a", "_b"),
}
