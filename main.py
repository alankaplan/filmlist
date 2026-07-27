#!/usr/bin/env python3
"""Entry point for the filmlist CLI.

Usage examples:
    python main.py pull 2023                 # pull all festivals' 2023 winners
    python main.py pull 2023 --festival Cannes
    python main.py list --festival Cannes
    python main.py generate -o index.html
"""

from filmlist.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
