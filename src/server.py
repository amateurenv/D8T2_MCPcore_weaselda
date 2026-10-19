"""Запуск: python3 -m src.server"""
import argparse
from pathlib import Path
from .storage import Storage
from .mcp_adapter import build_mcp_server

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(ROOT / "data/lavka.db"))
    parser.add_argument("--seed", default=str(ROOT / "data/seed.sql"))
    args = parser.parse_args()
    storage = Storage(args.db, args.seed)
    try:
        build_mcp_server(storage).run(transport="stdio", show_banner=False)
    finally:
        storage.close()

if __name__ == "__main__":
    main()

