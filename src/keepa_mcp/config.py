"""Runtime configuration for the Keepa MCP server.

All settings are read from environment variables (a local ``.env`` file is
loaded automatically if present). Nothing here requires editing the source.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the current working directory or the repository root, if any.
load_dotenv()

# Repository root = two levels up from this file (src/keepa_mcp/config.py).
REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_output_dir() -> Path:
    """Folder where XLSX reports are written.

    Defaults to ``<repo>/Продукты`` which, once this repo is cloned to the
    user's machine at ``E:/KEEPA``, resolves to the requested
    ``E:/KEEPA/Продукты`` directory. Override with KEEPA_OUTPUT_DIR.
    """
    raw = os.getenv("KEEPA_OUTPUT_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    return REPO_ROOT / "Продукты"


# --- Keepa API ---------------------------------------------------------------
KEEPA_API_KEY: str | None = os.getenv("KEEPA_API_KEY") or None

# Default Amazon marketplace. Keepa domain codes:
#   1=US 2=UK 3=DE 4=FR 5=JP 6=CA 8=IT 9=ES 10=IN 11=MX
DEFAULT_DOMAIN: str = os.getenv("KEEPA_DOMAIN", "US").strip().upper()

# How many days of stats Keepa should compute (avg/min/max windows).
DEFAULT_STATS_DAYS: int = int(os.getenv("KEEPA_STATS_DAYS", "90"))

# Default max number of ASINs returned by a product-finder search.
DEFAULT_SEARCH_LIMIT: int = int(os.getenv("KEEPA_SEARCH_LIMIT", "50"))

# --- Reports -----------------------------------------------------------------
OUTPUT_DIR: Path = _resolve_output_dir()


def ensure_output_dir() -> Path:
    """Create the report output directory if needed and return it."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def require_api_key() -> str:
    """Return the Keepa API key or raise a clear, actionable error."""
    if not KEEPA_API_KEY:
        raise RuntimeError(
            "KEEPA_API_KEY is not set. Add it to your environment or to a .env "
            "file in the project root (see .env.example). Get a key at "
            "https://keepa.com/#!api"
        )
    return KEEPA_API_KEY
