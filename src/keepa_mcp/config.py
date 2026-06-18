"""Runtime configuration for the Keepa MCP server.

All settings are read from environment variables. Two local files are loaded
automatically if present in the repository root:

- ``.env``       — standard dotenv file;
- ``ENV DOCS``   — the user's key file (``ENV DOCS``, ``ENV DOCS.txt``,
  ``ENV_DOCS`` …): either ``KEY=VALUE`` lines or a bare Keepa API key.

Nothing here requires editing the source.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the current working directory or the repository root, if any.
# override=True so the project's .env is the authoritative source of the key,
# even if a stale/empty value is present in the parent environment.
load_dotenv(override=True)

# Repository root = two levels up from this file (src/keepa_mcp/config.py).
REPO_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(REPO_ROOT / ".env", override=True)


def _load_env_docs() -> None:
    """Pick up KEEPA_API_KEY from an ``ENV DOCS`` file in the repo root.

    The user keeps the Keepa key in a file named "ENV DOCS" next to the
    project. Accept common spellings and two formats: ``KEY=VALUE`` lines or
    a single bare key token. Values never override an already-set variable.
    """
    candidates = [
        p
        for p in REPO_ROOT.iterdir()
        if p.is_file() and re.fullmatch(r"env[ _-]?docs(\.(txt|md|env))?", p.name, re.IGNORECASE)
    ] if REPO_ROOT.is_dir() else []

    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        bare_tokens: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip().upper(), value.strip().strip("'\"")
                if key and value and not os.getenv(key):
                    os.environ[key] = value
            elif re.fullmatch(r"[A-Za-z0-9]{40,}", line):
                bare_tokens.append(line)
        # A lone long token in the file is treated as the API key itself.
        if bare_tokens and not os.getenv("KEEPA_API_KEY"):
            os.environ["KEEPA_API_KEY"] = bare_tokens[0]


_load_env_docs()


def _resolve_output_dir() -> Path:
    """Folder where XLSX reports are written.

    Defaults to ``<repo>/Products`` which, on the user's machine where the
    repo lives at ``/home/andrea/KEEPA``, resolves to the requested
    ``/home/andrea/KEEPA/Products`` directory. Override with KEEPA_OUTPUT_DIR.
    """
    raw = os.getenv("KEEPA_OUTPUT_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    return REPO_ROOT / "Products"


# --- Keepa API ---------------------------------------------------------------
KEEPA_API_KEY: str | None = os.getenv("KEEPA_API_KEY") or None

# Markets we sell-research in, most mature first (used as the default order
# for multi-market searches).
MARKET_PRIORITY: list[str] = ["US", "UK", "DE", "FR", "IT", "ES"]

# Default Amazon marketplace. Keepa domain codes:
#   1=US 2=UK 3=DE 4=FR 5=JP 6=CA 8=IT 9=ES 10=IN 11=MX
DEFAULT_DOMAIN: str = os.getenv("KEEPA_DOMAIN", "US").strip().upper()

# How many days of stats Keepa should compute (avg/min/max windows).
DEFAULT_STATS_DAYS: int = int(os.getenv("KEEPA_STATS_DAYS", "90"))

# Default max number of ASINs returned by a product-finder search.
DEFAULT_SEARCH_LIMIT: int = int(os.getenv("KEEPA_SEARCH_LIMIT", "50"))

# --- Reports -----------------------------------------------------------------
OUTPUT_DIR: Path = _resolve_output_dir()

# --- Auto search ---------------------------------------------------------------
# Saved searches executed by ``keepa-auto`` (and the run_auto_search MCP tool)
# every 2 days. JSON file in the project root; see SEARCH_GUIDE.md.
AUTO_SEARCH_FILE: Path = Path(
    os.getenv("KEEPA_AUTO_SEARCH_FILE", "").strip() or (REPO_ROOT / "auto_searches.json")
).expanduser()


# --- China sourcing ----------------------------------------------------------
# The "find it cheaper in China" half of the workflow (see SOURCING_GUIDE.md).
# There is no paid marketplace API in the loop: Claude browses the Chinese
# sites itself (WebSearch / WebFetch / image search). These settings only tune
# which platforms to target and how to turn prices into comparable USD numbers.


def _csv_env(name: str, default: list[str]) -> list[str]:
    """Read a comma-separated env var into a list, falling back to ``default``."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return list(default)
    return [part.strip() for part in raw.split(",") if part.strip()]


# Chinese marketplaces to source from, in default search priority. Wholesale /
# B2B first (that is where sourcing margin lives). Override with CHINA_PLATFORMS.
CHINA_PLATFORMS: list[str] = _csv_env(
    "CHINA_PLATFORMS", ["1688", "alibaba", "taobao", "tmall", "pinduoduo"]
)

# Rough FX rates to USD, used to compare China offer prices against the Amazon
# reference price. These DRIFT over time — treat results as estimates and
# override via env (CHINA_USD_PER_CNY for the yuan, or a full CHINA_FX_TO_USD
# JSON map) when accuracy matters.
CHINA_FX_TO_USD: dict[str, float] = {
    "USD": 1.0, "CNY": 0.14, "RMB": 0.14, "EUR": 1.08, "GBP": 1.27,
    "JPY": 0.0064, "CAD": 0.73, "AED": 0.272, "MXN": 0.058, "BRL": 0.18, "INR": 0.012,
}

_usd_per_cny = os.getenv("CHINA_USD_PER_CNY", "").strip()
if _usd_per_cny:
    try:
        CHINA_FX_TO_USD["CNY"] = CHINA_FX_TO_USD["RMB"] = float(_usd_per_cny)
    except ValueError:
        pass

_fx_override = os.getenv("CHINA_FX_TO_USD", "").strip()
if _fx_override:
    try:
        import json as _json

        CHINA_FX_TO_USD.update(
            {str(k).upper(): float(v) for k, v in _json.loads(_fx_override).items()}
        )
    except Exception:  # noqa: BLE001 - bad override should not break startup
        pass

# Convenience: yuan->USD rate (also the default for unlabelled China prices).
CHINA_USD_PER_CNY: float = CHINA_FX_TO_USD["CNY"]

# Default extra freight as a fraction of unit cost when estimating landed cost
# (0 = ignore until the user supplies a real figure per run).
CHINA_FREIGHT_PCT: float = float(os.getenv("CHINA_FREIGHT_PCT", "0") or 0)

# Match score (0-1) at/above which a China offer is treated as a ~100% (EXACT)
# match even without an explicit image confirmation.
CHINA_EXACT_THRESHOLD: float = float(os.getenv("CHINA_EXACT_THRESHOLD", "0.9") or 0.9)

# Timeout (seconds) for the best-effort ``fetch_page`` helper.
CHINA_FETCH_TIMEOUT: float = float(os.getenv("CHINA_FETCH_TIMEOUT", "20") or 20)


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
