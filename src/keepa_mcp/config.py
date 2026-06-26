"""Runtime configuration for the Keepa MCP server.

The Keepa API key is resolved from the first of these that holds a real value,
in priority order:

1. the ``KEEPA_API_KEY`` **environment variable** — this is how Claude Code
   (web/MCP) and CI inject secrets, and it always wins;
2. a ``.env`` file in the project root (handy for local development);
3. an ``ENV DOCS`` file in the project root (``ENV DOCS``, ``ENV DOCS.txt``,
   ``ENV_DOCS`` …): either ``KEY=VALUE`` lines or a bare Keepa API key.

Note: a key stored only in GitHub *repository/Actions secrets* does **not**
reach this server — those are visible to GitHub Actions workflows, not to the
running MCP process. Put the key in one of the three places above.

Empty values, common placeholders (``your_keepa_api_key_here`` …) and
surrounding whitespace/quotes are ignored/stripped, so a half-finished ``.env``
copied from ``.env.example`` can no longer mask a real key.

Nothing here requires editing the source.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

# Repository root = two levels up from this file (src/keepa_mcp/config.py).
REPO_ROOT = Path(__file__).resolve().parents[2]

# Load .env from the current working directory and the repository root, if any.
# override=False so a real key injected via the environment (the Claude Code
# environment variable / CI secret) is always authoritative and a stale .env
# cannot clobber it. Placeholder/empty env values are handled in
# ``_resolve_api_key`` below, which falls back to the files when needed.
load_dotenv(override=False)
load_dotenv(REPO_ROOT / ".env", override=False)

# Values that look "set" but are not a real key — treated as absent.
_PLACEHOLDER_KEYS = {
    "your_keepa_api_key_here",
    "your_key",
    "your-key",
    "changeme",
    "change_me",
    "todo",
    "xxx",
    "none",
    "null",
}


def _clean_key(value: str | None) -> str | None:
    """Normalise a candidate key; return ``None`` if it is not a usable value.

    Strips surrounding whitespace and quotes (a trailing newline or stray
    quotes on a pasted secret is a common cause of silent 403s) and rejects
    empty strings and known placeholders.
    """
    if value is None:
        return None
    cleaned = value.strip().strip("'\"").strip()
    if not cleaned or cleaned.lower() in _PLACEHOLDER_KEYS:
        return None
    return cleaned


def _looks_like_keepa_key(value: str) -> bool:
    """Keepa keys are long alphanumeric tokens (typically 64 hex chars)."""
    return bool(re.fullmatch(r"[A-Za-z0-9]{40,}", value))


def _env_docs_key() -> str | None:
    """Pick up KEEPA_API_KEY (and side-set other KEY=VALUE) from ``ENV DOCS``.

    The user may keep the key in a file named "ENV DOCS" next to the project.
    Accept common spellings and two formats: ``KEY=VALUE`` lines or a single
    bare key token. Non-key ``KEY=VALUE`` pairs are exported only when unset;
    the Keepa key itself is returned for the central resolver to rank.
    """
    candidates = [
        p
        for p in REPO_ROOT.iterdir()
        if p.is_file() and re.fullmatch(r"env[ _-]?docs(\.(txt|md|env))?", p.name, re.IGNORECASE)
    ] if REPO_ROOT.is_dir() else []

    found: str | None = None
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip().upper(), _clean_key(value)
                if not key or not value:
                    continue
                if key == "KEEPA_API_KEY":
                    found = found or value
                elif not os.getenv(key):
                    os.environ[key] = value
            elif found is None and _looks_like_keepa_key(line):
                # A lone long token in the file is treated as the API key.
                found = line
    return found


def _resolve_api_key() -> str | None:
    """Resolve the Keepa key by priority: env var → .env file → ENV DOCS."""
    primary = _clean_key(os.getenv("KEEPA_API_KEY"))
    if primary:
        return primary

    # Env var missing or a placeholder — consult the files explicitly so a
    # placeholder in the environment cannot block a real key in .env.
    for env_path in (REPO_ROOT / ".env", Path.cwd() / ".env"):
        try:
            if env_path.is_file():
                candidate = _clean_key(dotenv_values(env_path).get("KEEPA_API_KEY"))
                if candidate:
                    return candidate
        except OSError:
            continue

    return _clean_key(_env_docs_key())


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
KEEPA_API_KEY: str | None = _resolve_api_key()

# Warn (don't crash) on a key that does not look like a Keepa key — catches a
# truncated/mangled secret early, since Keepa would otherwise just 403.
if KEEPA_API_KEY and not _looks_like_keepa_key(KEEPA_API_KEY):
    print(
        f"[keepa-mcp] warning: KEEPA_API_KEY ({len(KEEPA_API_KEY)} chars) does not "
        "look like a Keepa key (expected 40+ alphanumeric chars). Check for a "
        "truncated or mis-pasted value.",
        file=sys.stderr,
    )

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


def ensure_output_dir() -> Path:
    """Create the report output directory if needed and return it."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def require_api_key() -> str:
    """Return the Keepa API key or raise a clear, actionable error."""
    if not KEEPA_API_KEY:
        raise RuntimeError(
            "KEEPA_API_KEY is not set. Provide it in ONE of these places "
            "(checked in this order):\n"
            "  1. the KEEPA_API_KEY environment variable — for Claude Code "
            "(web/MCP) add it as an environment variable in your Claude Code "
            "environment settings;\n"
            "  2. a .env file in the project root (see .env.example);\n"
            "  3. an 'ENV DOCS' file in the project root.\n"
            "Note: a GitHub repository/Actions secret is NOT enough — it is "
            "only visible to GitHub Actions, not to this server. "
            "Get a key at https://keepa.com/#!api"
        )
    return KEEPA_API_KEY
