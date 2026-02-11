# %% [markdown]
# # Ticker Prep
#
# Notebook-style `.py` file (with `# %%` cell separators).
#
# Loads and displays every top-level item from each `*.toml` file in
# `src/backend/app/security_scan/config/`.

# %%
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any
import html
import pprint
import sys
import tomllib


def _find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "src" / "backend" / "app").exists():
            return candidate
    raise RuntimeError(
        f"Could not locate repo root from {start}. Expected to find src/backend/app."
    )


try:
    _THIS_FILE = Path(__file__).resolve()
except NameError:  # when executed as notebook cells, __file__ may be undefined
    _THIS_FILE = None

_START_PATH = _THIS_FILE.parent if _THIS_FILE is not None else Path.cwd().resolve()
REPO_ROOT = _find_repo_root(_START_PATH)

# Ensure `import app.*` works in notebook execution contexts.
BACKEND_SRC = REPO_ROOT / "src" / "backend"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))


def _safe_display(value: Any) -> None:
    """Prefer rich Jupyter display when available; fall back to plain printing."""

    try:
        from IPython.display import display  # type: ignore

        display(value)
        return
    except Exception:
        pass

    print(value)


def _as_pretty_text(value: Any) -> str:
    return pprint.pformat(value, sort_dicts=True, width=100)


def _safe_display_scrollbox(
    title: str, lines: list[str], max_height_px: int = 320
) -> None:
    """Render large text as a scrollbox in notebooks; fall back to plain text."""

    text = "\n".join(lines)
    try:
        from IPython.display import HTML, display  # type: ignore

        escaped_title = html.escape(title)
        escaped_text = html.escape(text)
        display(
            HTML(
                f"""
<h3 style="margin: 0 0 8px 0;">{escaped_title}</h3>
<div style="max-height:{max_height_px}px; overflow:auto; border:1px solid #ddd; padding:10px; white-space:pre; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;">{escaped_text}</div>
""".strip()
            )
        )
        return
    except Exception:
        pass

    print(f"\n## {title}")
    print(text)


def _display_section(section_name: str, value: Any) -> None:
    print(f"\n## {section_name}")

    if is_dataclass(value):
        value = asdict(value)

    if isinstance(value, dict):
        for key, item in value.items():
            _display_section(f"{section_name}.{key}", item)
        return

    if isinstance(value, list):
        print(f"type=list len={len(value)}")
        if all(isinstance(x, str) for x in value):
            _safe_display_scrollbox(section_name, [str(x) for x in value])
            return

        _safe_display(_as_pretty_text(value))
        return

    print(f"type={type(value).__name__}")
    _safe_display(_as_pretty_text(value))


def load_toml_file(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


# %%
CONFIG_DIR = REPO_ROOT / "src" / "backend" / "app" / "security_scan" / "config"
TOML_FILES = sorted(CONFIG_DIR.glob("*.toml"))

print("Repo root:", REPO_ROOT)
print("Config dir:", CONFIG_DIR)
print("TOML files:")
for p in TOML_FILES:
    print(" -", p.relative_to(REPO_ROOT))

# %%
# Load and display every top-level item from each TOML file.

loaded_configs: dict[str, dict[str, Any]] = {}

for toml_path in TOML_FILES:
    print("\n" + "=" * 88)
    print("FILE:", toml_path.relative_to(REPO_ROOT))
    print("=" * 88)

    try:
        data = load_toml_file(toml_path)
    except Exception as exc:
        print("ERROR: could not parse TOML")
        print(f"{type(exc).__name__}: {exc}")
        continue

    loaded_configs[toml_path.name] = data
    if not data:
        print("(empty)")
        continue

    for top_level_key, top_level_value in data.items():
        _display_section(top_level_key, top_level_value)

# %%
# Convenience: extract the key ticker lists from `securities.toml`.

securities_raw = loaded_configs.get("securities.toml") or load_toml_file(
    CONFIG_DIR / "securities.toml"
)
print("\nRaw securities.toml keys:", list(securities_raw.keys()))


def _get_ticker_list(config: dict[str, Any], table_name: str) -> list[str]:
    table = config.get(table_name)
    if not isinstance(table, dict):
        return []
    raw = table.get("list")
    if not isinstance(raw, list):
        return []
    return [item.strip() for item in raw if isinstance(item, str) and item.strip()]


tickers_list = _get_ticker_list(securities_raw, "tickers")
nasdaq_tickers_list = _get_ticker_list(securities_raw, "nasdaq_tickers")
sp100_tickers_list = _get_ticker_list(securities_raw, "sp100_tickers")

print("Securities ticker lists:")
print(" - tickers.list:", len(tickers_list))
print(" - nasdaq_tickers.list:", len(nasdaq_tickers_list))
print(" - sp100_tickers.list:", len(sp100_tickers_list))

if tickers_list:
    _safe_display_scrollbox("tickers.list", tickers_list)
if nasdaq_tickers_list:
    _safe_display_scrollbox("nasdaq_tickers.list", nasdaq_tickers_list)
if sp100_tickers_list:
    _safe_display_scrollbox("sp100_tickers.list", sp100_tickers_list)

# %%
# Optional: also show the "typed" merged config the CLI uses.
#
# Note: `SecurityScanConfig` intentionally only models the specific fields the CLI
# consumes. It does not include auxiliary lists like `nasdaq_tickers` or
# `sp100_tickers`.

try:
    from app.security_scan.config_loader import load_security_scan_config

    typed_config = load_security_scan_config(CONFIG_DIR)
    typed_dict = asdict(typed_config)

    print("\n" + "=" * 88)
    print("Typed config keys:")
    print("=" * 88)
    print(typed_dict.keys())

    _display_section("typed_config", typed_dict)
except Exception as exc:
    print("\nNote: could not load typed SecurityScanConfig.")
    print(f"{type(exc).__name__}: {exc}")

# %%
print(asdict(typed_config).keys())
# %%
type(securities_raw)
# %%
securities_raw.keys()
# %%
tick = set(securities_raw['tickers']['list'])
ndx = set(securities_raw['nasdaq_tickers']['list'])
sp100 = set(securities_raw['sp100_tickers']['list'])
# %%
tick = tick.union(ndx).union(sp100)
tick = sorted(list(tick))
ndx = sorted(list(ndx))
sp100 = sorted(list(sp100))
print()
# %%
