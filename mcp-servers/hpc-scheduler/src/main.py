#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.server import UnifiedMCPServer  # noqa: E402


def main() -> None:
    server = UnifiedMCPServer()
    server.load()
    server.run()


if __name__ == "__main__":
    main()
