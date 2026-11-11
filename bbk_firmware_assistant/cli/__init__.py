from __future__ import annotations

from ._common import ask_select
from .bloat import flow_bloat, flow_bloat_flash
from .download import flow_download
from .extract import flow_extract
from .flash import flow_flash

ACTIONS = {
    "Download OTA firmware": flow_download,
    "Download bloat images": flow_bloat,
    "Extract OTA firmware": flow_extract,
    "Flash firmware": flow_flash,
    "Flash bloat images": flow_bloat_flash,
}


def main() -> None:
    while True:
        choice = ask_select("Action:", [*ACTIONS, "Quit"])
        if not choice or choice == "Quit":
            break
        try:
            ACTIONS[choice]()
        except KeyboardInterrupt:
            print("  (interrupted)")