#!/usr/bin/env python3
"""Entry point for the filmlist CLI.

Usage examples:
    python main.py seed
    python main.py add "Some Film" 2024 Cannes --director "A. Director"
    python main.py list --festival Cannes
    python main.py generate -o index.html
"""

from filmlist.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
