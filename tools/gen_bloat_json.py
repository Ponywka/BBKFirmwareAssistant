#!/usr/bin/env python3
"""Generate bbk_firmware_assistant/data/bloat.json from the Flasher_Builder assets manifest.

The output JSON is what the assistant actually reads at runtime: per-model
directories with full download URLs and final file names, no name parsing.
Regenerate after the upstream manifest changes:

    .venv/bin/python tools/gen_bloat_json.py /path/to/assets-manifest.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT_MANIFEST = "/home/ponywka/Projects/Flasher_Builder/bloat/assets-manifest.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "bbk_firmware_assistant" / "data" / "bloat.json"

# Asset name formats:
#   bloat-<device>-<region>_BLOAT-<partition>-<hash>.img[.gz]
#   bloat-<device>-<TAG>-<partition>-<hash>.img[.gz]   (TAG = FIXES, COS_FILES_HERE; no region)
_NAME_RE = re.compile(r"^bloat-(?P<device>[^-]+)-(?P<rest>.+)\.(?:img\.gz|img)$")
_HASH_RE = re.compile(r"^[0-9a-f]{12}$")

# (device, region) -> model code (top-level dir under bloat/; region becomes a subdir).
# Model codes parsed from roms.danielspringer.at data-devices (version strings embed the
# model code, e.g. CPH2747_16.0.7.201(EX01)).
MODEL_DIRS: dict[tuple[str, str], str] = {
    ("13", "CN"): "PJZ110",
    ("13", "EUGLO"): "CPH2653",
    ("13", "IN"): "CPH2649",
    ("13", "NA"): "CPH2655",
    ("13R", "CN"): "PKG110",  # CN 13R = Ace 5
    ("13R", "EUGLO"): "CPH2645",
    ("13R", "IN"): "CPH2691",
    ("13R", "NA"): "CPH2645",
    ("13S", "IN"): "CPH2723",
    ("13T", "CN"): "PKX110",
    ("15", "CN"): "PLK110",
    ("15", "GLO"): "CPH2747",
    ("15", "EU"): "CPH2747",
    ("15", "IN"): "CPH2745",
    ("15", "NA"): "CPH2749",
    ("15R", "GLO"): "CPH2769",
    ("15R", "EU"): "CPH2769",
    ("15R", "IN"): "CPH2767",
    ("15T", "CN"): "PLZ110",
    ("15T", "GLO"): "PLZ110",
    ("Ace5", "A5P"): "PKG110",
    ("Ace5", "EUGLO"): "PKG110",
    ("Ace6", "CN"): "PLQ110",
    ("Ace6T", "CN"): "PLR110",
    ("Ace6T", "EU"): "PLR110",
    ("Ace6T", "GLO"): "PLR110",
    ("Ace6T", "IN"): "PLR110",
    ("GT7Pro", "CN"): "RMX5010",
    ("GT7Pro", "EU"): "RMX5011",
    ("NEO8", "CN"): "RMX8899",
    ("Pad2Pro", "CN"): "OPD2413",
    ("Pad2Pro", "EU"): "OPD2413",
    ("Pad2Pro", "GLO"): "OPD2413",
    ("Pad3Pro", "CN"): "OPD2513",
    ("X9U", "APC"): "CPH2841",
    ("X9U", "ID"): "CPH2841",
    ("X9U", "IN"): "CPH2841",
    ("X9U", "JP"): "CPH2841",
    ("X9U", "MX"): "CPH2841",
    ("X9U", "MY"): "CPH2841",
    ("X9U", "SG"): "CPH2841",
    ("X9U", "TH"): "CPH2841",
    ("X9U", "TW"): "CPH2841",
    ("X9U", "VN"): "CPH2841",
}

# Skipped on purpose: conversion-fixup groups without a region (COS_FILES_HERE, FIXES)
# and X9U CN (ambiguous model: the site lists both PMA110 and PMA120).
TAGS = {"COS_FILES_HERE", "FIXES"}
EXCLUDED: set[tuple[str, str]] = {
    ("X9U", "CN"),
}

# Complete per-ROM file sets for the 15 family, as served by Flasher_Builder:
# my_company comes from the CN asset for every region, system_dlkm_oki falls back
# to the EU asset when the region has none. Each row: dest filename -> source asset.
Ace6T_PRELOAD = {"CN": ("Ace6T", "CN", "my_preload"), "EU": ("15R", "EU", "my_preload"),
                 "GLO": ("15R", "GLO", "my_preload"), "IN": ("15R", "IN", "my_preload")}
Ace6T_OKI = {"CN": ("Ace6T", "CN", "system_dlkm_oki"), "EU": ("15R", "EU", "system_dlkm_oki"),
             "GLO": ("15R", "EU", "system_dlkm_oki"), "IN": ("15R", "IN", "system_dlkm_oki")}
ROM_SETS: dict[tuple[str, str], list[tuple[str, tuple[str, str, str]]]] = {}
for _r in ("CN", "EU", "GLO", "IN", "NA"):
    ROM_SETS[("15", _r)] = [
        ("my_company.img", ("15", "CN", "my_company")),
        ("my_preload.img", ("15", _r, "my_preload")),
        ("system_dlkm_oki.img", ("15", "CN" if _r == "CN" else "EU", "system_dlkm_oki")),
    ]
for _r in ("EU", "GLO", "IN"):
    ROM_SETS[("15R", _r)] = [
        ("my_company.img", ("15", "CN", "my_company")),
        ("my_preload.img", ("15R", _r, "my_preload")),
        ("system_dlkm_oki.img", ("15R", "IN" if _r == "IN" else "EU", "system_dlkm_oki")),
    ]
for _r in ("CN", "EU", "GLO", "IN"):
    ROM_SETS[("Ace6T", _r)] = [
        ("my_company.img", ("15", "CN", "my_company")),
        ("my_preload.img", Ace6T_PRELOAD[_r]),
        ("system_dlkm_oki.img", Ace6T_OKI[_r]),
    ]
ROM_SETS[("15T", "CN")] = [
    ("my_company.img", ("15", "CN", "my_company")),
    ("my_preload.img", ("15T", "CN", "my_preload")),
    ("system_dlkm_oki.img", ("15T", "CN", "system_dlkm_oki")),
]
ROM_SETS[("15T", "GLO")] = [
    ("my_preload.img", ("15T", "GLO", "my_preload")),
]


def parse_asset_name(name: str) -> tuple[str, str, str] | None:
    """Split an asset name into (device, region_or_tag, partition)."""
    m = _NAME_RE.match(name)
    if not m:
        return None
    partition, sep, tail = m["rest"].rpartition("-")
    if not sep or not _HASH_RE.match(tail):
        return None
    group, sep, partition = partition.rpartition("-")
    if not sep:
        return None
    return m["device"], group.removesuffix("_BLOAT"), partition


def generate(manifest_path: Path) -> dict:
    data = json.loads(manifest_path.read_text())
    catalog: dict[str, dict[str, dict]] = defaultdict(dict)

    def add(model: str, region: str, filename: str, entry: dict) -> None:
        slot = catalog[model].setdefault(region, {}).get(filename)
        if slot is not None:
            if slot["sha256"] == entry["sha256"]:
                return  # same asset already placed here
            raise SystemExit(
                f"collision: {model}/{region}/{filename}: "
                f"{slot['url'].rsplit('/', 1)[-1]} vs {entry['asset_name']}"
            )
        catalog[model].setdefault(region, {})[filename] = {
            "url": "https://github.com/{repository}/releases/download/{tag}/{asset_name}".format(
                repository=data["repository"], tag=data["tag"], asset_name=entry["asset_name"]
            ),
            "bytes": entry["bytes"],
            "sha256": entry["sha256"],
            "raw_bytes": entry["raw_bytes"],
            "raw_sha256": entry["raw_sha256"],
            "encoding": entry["encoding"],
        }

    parsed: dict[tuple[str, str, str], dict] = {}
    for entry in data["assets"].values():
        p = parse_asset_name(entry["asset_name"])
        if p is None:
            print(f"  ! unparsed asset name: {entry['asset_name']}", file=sys.stderr)
            continue
        device, group, partition = p
        if group in TAGS or (device, group) in EXCLUDED:
            continue  # conversion fixups and ambiguous entries — not in the catalog
        if (device, group) not in MODEL_DIRS:
            raise SystemExit(
                f"no model code for {device} {group} — add it to MODEL_DIRS in this script"
            )
        parsed[(device, group, partition)] = entry

    # Complete ROM sets first (assets consumed there are not placed region-scoped).
    consumed: set[tuple[str, str, str]] = set()
    for (device, region), rows in ROM_SETS.items():
        model = MODEL_DIRS[(device, region)]
        for filename, src in rows:
            if src not in parsed:
                raise SystemExit(f"ROM set {device}/{region}: asset {src} not in manifest")
            consumed.add(src)
            add(model, region, filename, parsed[src])

    # Everything else: the asset goes into its own region dir.
    for (device, group, partition), entry in parsed.items():
        if (device, group) in ROM_SETS:
            continue
        add(MODEL_DIRS[(device, group)], group, f"{partition}.img", entry)

    return dict(sorted(catalog.items()))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest", nargs="?", default=DEFAULT_MANIFEST, type=Path)
    ap.add_argument("-o", "--output", default=DEFAULT_OUTPUT, type=Path)
    args = ap.parse_args()

    catalog = generate(args.manifest)
    total = sum(len(files) for regions in catalog.values() for files in regions.values())
    args.output.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")
    print(f"{total} files across {len(catalog)} models -> {args.output}")


if __name__ == "__main__":
    main()
