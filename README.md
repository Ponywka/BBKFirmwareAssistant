# BBK Firmware Assistant

Interactive CLI for downloading, extracting, and flashing OTA firmware for
BBK-family devices — **OnePlus**, **OPPO**, and **Realme**.

It walks you through the whole pipeline with a terminal menu:

1. **Download** an OTA package straight from the official Oplus update servers
   (or from a custom URL).
2. **Extract** the partition images from the package's `payload.bin`.
3. **Flash** those images to a device over `fastboot`, with a guided,
   step-by-step procedure and a dry-run mode.

> ⚠️ **Warning:** Flashing firmware can brick your device and will usually void
> your warranty. You do this at your own risk. Always start with **Dry-run**
> mode to review the exact `fastboot` commands before writing anything.

## Requirements

- **Python 3.10+**
- Python packages from `requirements.txt`
- External command-line tools (must be on your `PATH`):

  | Tool | Needed for |
  | --- | --- |
  | [`payload-dumper-go`](https://github.com/ssut/payload-dumper-go/releases) | unpacking `payload.bin` into `.img` files |
  | `fastboot` (Android platform-tools) | writing images to the device |
  | `aria2c`, `wget`, or `curl` | fetching the OTA package (at least one) |

## Installation

```bash
git clone https://github.com/Ponywka/BBKFirmwareAssistant.git BBKFirmwareAssistant
cd BBKFirmwareAssistant
python3 -m venv .venv
source .venv/bin/activate # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Install the external tools for your platform, e.g. on Debian/Ubuntu:

```bash
sudo apt install android-tools-fastboot aria2
# payload-dumper-go: download from the releases page and place on your PATH
```

## Usage

Run the interactive assistant:

```bash
python main.py
```

Pick an action from the menu and follow the prompts. Press **Ctrl-C** at any
prompt to cancel the current step and return to the menu.

### Download

Choose your vendor (OnePlus / OPPO / Realme), device, and revision. The tool
queries the OTA server, picks a download method (`aria2c` / `wget` / `curl`),
and saves the package. Completed `.zip` packages are automatically renamed to
their `version_name` from the embedded OTA metadata. You can also paste a
**custom link** to download directly.

### Extract

Select a downloaded `.zip` (or a raw `payload.bin`) from the `downloads`
folder, or enter a path manually. The tool extracts `payload.bin` and runs
`payload-dumper-go` to produce the partition `.img` files, ready for flashing.

### Flash

Select an extracted firmware directory from the `firmware` folder. Choose:

- **Mode** — *Dry-run* (print commands only) or *Flash* (write to device).
- **Android version** on the device (`13-15`, `12`, or `10-11`) — this affects
  the logical-partition handling.

The assistant then guides you through bootloader/fastbootd reboots and flashes
each partition group to both A/B slots, with retry prompts on failure. At the
end you can reboot to system, wipe data, or leave the device as-is.

## Working directories

These are created in the directory you run the tool from (the current working
directory), so each project/working folder keeps its own files:

| Path | Purpose |
| --- | --- |
| `./downloads` | Downloaded OTA packages |
| `./firmware/<version>` | Extracted partition images |

## Acknowledgements

This tool is based on and inspired by the following projects, used as reference
for the OTA download and flashing logic:

- **[OplusUpdater](https://pkg.go.dev/github.com/Houvven/OplusUpdater)** — reference for the code that queries the BBK OTA servers.
- **[Link Resolver and Downloader](https://4pda.to/forum/index.php?showtopic=1096928&view=findpost&p=139997614)** — reference for resolving OTA links and
  downloading firmware packages.
- **[Fastboot Firmware Flasher](https://4pda.to/forum/index.php?showtopic=1032195&view=findpost&p=133090516)** — reference for the fastboot flashing
  procedure and partition handling.

## Disclaimer

This is an unofficial tool and is not affiliated with OnePlus, OPPO, Realme, or
BBK Electronics. Use it responsibly and only on devices you own.