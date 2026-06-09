"""Quick setup check for the Keepa MCP server.

Run from the project root after configuring .env:

    uv run python check_setup.py

Prints the resolved configuration and, if a key is present, performs a live
Keepa call to confirm the key works and show the remaining token quota.
"""

from __future__ import annotations

import json


def main() -> int:
    from keepa_mcp import config, server

    info = server.server_info()
    print("=== Configuration ===")
    print(json.dumps(info, ensure_ascii=False, indent=2))

    if not info.get("api_key_configured"):
        print("\n[X] KEEPA_API_KEY is NOT set.")
        print("    Add it to a .env file in this folder:")
        print("        KEEPA_API_KEY=your_key")
        print("    (.env must sit next to pyproject.toml; get a key at")
        print("     https://keepa.com/#!api)")
        return 1

    print("\n[OK] API key detected. Testing a live Keepa call...")
    try:
        from keepa_mcp import keepa_client

        status = keepa_client.tokens_left()
        print("=== Keepa token status ===")
        print(json.dumps(status, ensure_ascii=False, indent=2))
        print("\n[OK] Key is valid. Reports will be written to:")
        print(f"     {config.OUTPUT_DIR}")
        return 0
    except Exception as exc:  # noqa: BLE001 - surface any auth/network error plainly
        print(f"\n[X] Keepa call failed: {type(exc).__name__}: {exc}")
        print("    Likely an invalid key or no active Keepa API subscription.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
