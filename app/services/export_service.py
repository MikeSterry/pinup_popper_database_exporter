"""Export service: generates /output/puplookup.csv based on local cached data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import csv
import json
import re

from app.exceptions.custom_exceptions import DataValidationError
from app.utils.logger import get_logger

log = get_logger(__name__)

# Legacy/source template columns sometimes found in the GitHub CSV.
BASE_COLUMNS = [
    "GameFileName",
    "GameName",
    "Manufact",
    "GameYear",
    "NumPlayers",
    "GameType",
    "Category",
    "GameTheme",
    "WebLinkURL",
    "IPDBNum",
    "AltRunMode",
    "DesignedBy",
    "Author",
    "GAMEVER",
    "Rom",
    "Tags",
    "VPS-ID",
]

# Final/output columns expected by the current app/export.
OUT_COLUMNS = [
    "GameFileName",
    "GameName",
    "Manufact",
    "GameYear",
    "NumPlayers",
    "GameType",
    "Category",
    "GameTheme",
    "WebLinkURL",
    "WebLink2URL",
    "IPDBNum",
    "AltRunMode",
    "DesignedBy",
    "Author",
    "GAMEVER",
    "Rom",
    "Tags",
    "VPS-ID",
    "WebGameID",
    "MasterID",
]

YEAR_RE = re.compile(r"^\d{4}$")
VPS_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,}$")
WEBLINK2_BASE = "https://virtualpinballspreadsheet.github.io/tables"


def _norm_weblink(url: str) -> str:
    """Keep only IPDB links; drop placeholders and non-IPDB sources."""
    if not url:
        return ""

    value = url.strip()
    if value.lower() in {"not available", "n/a", "na", "none"}:
        return ""
    if "ipdb.org" not in value.lower():
        return ""
    return value


def _parse_ipdb_num(ipdb_url: str) -> str:
    """Extract numeric machine id from an IPDB URL, if present."""
    if not ipdb_url:
        return ""

    match = re.search(r"(?:id=|machine\.cgi\?id=)(\d+)", ipdb_url)
    return match.group(1) if match else ""


def _excluded_feature(feature: str) -> bool:
    """Exclude noisy feature tags."""
    value = feature.strip()
    return value.lower().startswith("incl.") or value == "no ROM"


def _weblink2(master_id: str, vps_id: str) -> str:
    """Build WebLink2URL as seen in the website export."""
    if not master_id or not vps_id:
        return ""
    return f"{WEBLINK2_BASE}?game={master_id}&fileType=tables&fileId={vps_id}"


def _sanitize_filename_part(value: str) -> str:
    """Mimic observed behavior (e.g., 50/50 -> 50_50)."""
    return value.replace("/", "_")


def _blank_out_row() -> Dict[str, str]:
    """Create a blank OUT_COLUMNS-shaped row dict."""
    return {column: "" for column in OUT_COLUMNS}


def _row_to_dict(header: List[str], row: List[str]) -> Dict[str, str]:
    """Zip a CSV row to its header safely."""
    return {column: row[idx] if idx < len(row) else "" for idx, column in enumerate(header)}


def _normalize_template_row(header: List[str], row: List[str]) -> Optional[Dict[str, str]]:
    """
    Normalize a raw template row into the OUT_COLUMNS shape.

    Supports:
    - legacy 17-column BASE_COLUMNS rows
    - current 20-column OUT_COLUMNS rows
    - malformed legacy rows where manufacturer was split at a comma
    - extra-column rows where overflow should be folded into Tags
    """
    normalized = _blank_out_row()

    # Exact modern row shape.
    if header == OUT_COLUMNS:
        if len(row) < len(OUT_COLUMNS):
            padded = row + [""] * (len(OUT_COLUMNS) - len(row))
        else:
            padded = row[: len(OUT_COLUMNS)]

        row_dict = _row_to_dict(OUT_COLUMNS, padded)
        vps_id = row_dict.get("VPS-ID", "").strip()
        if not VPS_ID_RE.match(vps_id):
            return None

        normalized.update(row_dict)
        return normalized

    # Exact legacy row shape.
    if header == BASE_COLUMNS:
        fixed = list(row)

        # Case A: 18 columns because manufacturer was split at a comma and year shifted.
        if len(fixed) == len(BASE_COLUMNS) + 1:
            if (not YEAR_RE.match(fixed[3].strip())) and YEAR_RE.match(fixed[4].strip()):
                fixed[2] = f"{fixed[2].rstrip()}, {fixed[3].lstrip()}"
                del fixed[3]

        # Case B: overflow fields; fold extras into Tags and keep last as VPS-ID.
        if len(fixed) > len(BASE_COLUMNS):
            extras = fixed[len(BASE_COLUMNS):]
            fixed = fixed[: len(BASE_COLUMNS)]

            candidate_vps = extras[-1].strip()
            if not VPS_ID_RE.match(candidate_vps):
                return None

            merged_tags = fixed[15].strip()
            if fixed[16].strip() and not VPS_ID_RE.match(fixed[16].strip()):
                merged_tags = f"{merged_tags} {fixed[16].strip()}".strip() if merged_tags else fixed[16].strip()

            for token in extras[:-1]:
                token = token.strip()
                if token:
                    merged_tags = f"{merged_tags} {token}".strip() if merged_tags else token

            fixed[15] = merged_tags
            fixed[16] = candidate_vps

        if len(fixed) != len(BASE_COLUMNS):
            return None

        if not VPS_ID_RE.match(fixed[16].strip()):
            return None

        base_dict = _row_to_dict(BASE_COLUMNS, fixed)
        for column in BASE_COLUMNS:
            normalized[column] = base_dict.get(column, "")

        # Derived/modern-only columns remain blank here and are filled later.
        return normalized

    # Fallback: map any known columns that happen to exist in the source header.
    row_dict = _row_to_dict(header, row)

    vps_id = row_dict.get("VPS-ID", "").strip()
    if not VPS_ID_RE.match(vps_id):
        return None

    for column in OUT_COLUMNS:
        if column in row_dict:
            normalized[column] = row_dict[column]

    return normalized


@dataclass(frozen=True)
class TableCtx:
    """Enrichment context for a tableFiles entry."""

    game_id: str
    game_name: str
    manufacturer: str
    year: str
    players: str
    game_type: str
    theme: str
    designers: str
    ipdb_url: str
    ipdb_num: str
    authors: List[str]
    version: str
    tags_list: List[str]
    edition: str
    created_at: int
    tf_index: int
    tf_gamefile_name: str


def _build_indexes(vpsdb: List[Dict[str, Any]]) -> Dict[str, TableCtx]:
    """Map tableFiles[].id -> TableCtx."""
    out: Dict[str, TableCtx] = {}

    for game in vpsdb:
        if not isinstance(game, dict):
            continue

        base_name = game.get("name") or ""
        manufacturer = game.get("manufacturer") or ""

        year = game.get("year")
        if isinstance(year, (int, float)) and year is not None:
            year_s = str(int(year))
        else:
            year_s = str(year) if year is not None else ""

        players = game.get("players")
        if players is None:
            players_s = ""
        elif isinstance(players, (int, float)):
            players_s = str(int(players))
        else:
            players_s = str(players)

        game_type = game.get("type") or ""

        theme = game.get("theme")
        theme_s = ", ".join(theme) if isinstance(theme, list) else (theme or "")

        designers = game.get("designers")
        designers_s = ", ".join(designers) if isinstance(designers, list) else ""

        ipdb_url = _norm_weblink(game.get("ipdbUrl") or "")
        ipdb_num = _parse_ipdb_num(ipdb_url)

        table_files = game.get("tableFiles") or []
        for index, table_file in enumerate(table_files):
            if not isinstance(table_file, dict):
                continue

            vps_id = table_file.get("id")
            if not vps_id:
                continue

            edition = table_file.get("edition") or ""
            tf_gamefile_name = table_file.get("gameFileName") or ""

            name_with_edition = base_name
            if edition and edition.lower() not in base_name.lower():
                name_with_edition = f"{base_name} - {edition}"

            game_name = (
                f"{name_with_edition} ({manufacturer} {year_s})"
                if manufacturer and year_s
                else name_with_edition
            )

            authors = table_file.get("authors") or []
            if isinstance(authors, str):
                authors = [authors]
            authors = [author for author in authors if isinstance(author, str)]

            version = table_file.get("version") or ""

            features = table_file.get("features") or []
            tags_list = [
                feature
                for feature in features
                if isinstance(feature, str) and feature.strip() and not _excluded_feature(feature)
            ]

            created_at = table_file.get("createdAt") or 0

            out[vps_id] = TableCtx(
                game_id=((table_file.get("game") or {}).get("id") or game.get("id") or ""),
                game_name=game_name,
                manufacturer=manufacturer,
                year=year_s,
                players=players_s,
                game_type=game_type,
                theme=theme_s,
                designers=designers_s,
                ipdb_url=ipdb_url,
                ipdb_num=ipdb_num,
                authors=authors,
                version=version,
                tags_list=tags_list,
                edition=edition,
                created_at=int(created_at) if isinstance(created_at, (int, float)) else 0,
                tf_index=index,
                tf_gamefile_name=tf_gamefile_name,
            )

    return out


def _build_master_map(vpsdb: List[Dict[str, Any]]) -> Dict[str, str]:
    """Map tableFiles[].id -> game.id (MasterID)."""
    out: Dict[str, str] = {}

    for game in vpsdb:
        if not isinstance(game, dict):
            continue

        game_id = game.get("id") or ""

        for table_file in (game.get("tableFiles") or []):
            if not isinstance(table_file, dict):
                continue

            vps_id = table_file.get("id")
            if not vps_id:
                continue

            tf_game = table_file.get("game") or {}
            master_id = (tf_game.get("id") if isinstance(tf_game, dict) else "") or game_id
            out[vps_id] = master_id

    return out


def _raw_gamefile_name_is_richer(raw_name: str, base: str, author_part: str, version_part: str, tags_upper: set[str]) -> bool:
    """Return True only when raw tableFiles[].gameFileName is clearly richer than the composed base."""
    raw = (raw_name or "").strip()
    if not raw or raw == base:
        return False

    raw_lower = raw.lower()

    has_author = bool(author_part and author_part.lower() in raw_lower)
    has_version = bool(version_part and version_part.lower() in raw_lower)
    has_mod = bool("MOD" in tags_upper and " mod" in f" {raw_lower}")
    has_vr = bool("VR" in tags_upper and " vr" in f" {raw_lower}")

    return has_author or has_version or has_mod or has_vr


def _build_gamefile_name(ctx: TableCtx) -> str:
    """
    Build GameFileName.

    Prefer a composed name unless tableFiles[].gameFileName is clearly richer.
    This avoids returning short/base names that omit author/version/tag suffixes.
    """
    base = _sanitize_filename_part(ctx.game_name)

    author_part = ctx.authors[0].strip() if ctx.authors else ""
    version_part = (ctx.version or "").strip()
    tags_upper = {tag.strip().upper() for tag in ctx.tags_list if isinstance(tag, str)}

    parts = [base]

    if author_part:
        parts.append(author_part)

    if version_part:
        parts.append(version_part)

    if "MOD" in tags_upper:
        parts.append("MOD")

    if "VR" in tags_upper:
        parts.append("VR")

    composed = " ".join(part for part in parts if part).strip()
    raw_name = (ctx.tf_gamefile_name or "").strip()

    if _raw_gamefile_name_is_richer(raw_name, base, author_part, version_part, tags_upper):
        return raw_name

    return composed


def _sort_key_for_ctx(ctx: TableCtx) -> Tuple:
    """Match site ordering: name prefix, createdAt desc, edition empty first, file order."""
    prefix = ctx.game_name.split(" (", 1)[0]
    return (prefix, -ctx.created_at, 0 if not ctx.edition else 1, ctx.tf_index)


def _generate_rows(
    template_rows: List[Dict[str, str]],
    ctx_by_vpsid: Dict[str, TableCtx],
    master_by_vpsid: Dict[str, str],
) -> List[List[str]]:
    """Enrich and sort rows to match the site export."""
    out_rows: List[List[str]] = [OUT_COLUMNS]

    for template_row in template_rows:
        row = _blank_out_row()
        row.update(template_row)

        vps_id = row["VPS-ID"]
        ctx = ctx_by_vpsid.get(vps_id)

        if not ctx:
            master = row.get("MasterID", "").strip()
            if not master:
                master = row.get("WebGameID", "").strip()

            if not row.get("WebLink2URL", "").strip():
                row["WebLink2URL"] = _weblink2(master, vps_id) if master else ""

            row["WebGameID"] = row.get("WebGameID", "").strip()
            row["MasterID"] = master
            out_rows.append([row.get(column, "") for column in OUT_COLUMNS])
            continue

        master = master_by_vpsid.get(vps_id, ctx.game_id)
        row["WebLink2URL"] = _weblink2(master, vps_id) if master else ""
        row["WebGameID"] = row.get("WebGameID", "").strip()
        row["MasterID"] = master

        # Overwrite with vpsdb-derived truth.
        row["GameName"] = ctx.game_name
        row["Manufact"] = ctx.manufacturer
        row["GameYear"] = ctx.year
        row["NumPlayers"] = ctx.players
        row["GameType"] = ctx.game_type
        row["GameTheme"] = ctx.theme
        row["WebLinkURL"] = ctx.ipdb_url
        row["IPDBNum"] = ctx.ipdb_num
        row["DesignedBy"] = ctx.designers
        row["Author"] = ", ".join(ctx.authors)
        row["GAMEVER"] = ctx.version
        row["Tags"] = ", ".join(ctx.tags_list)
        row["GameFileName"] = _build_gamefile_name(ctx)

        out_rows.append([row.get(column, "") for column in OUT_COLUMNS])

    data_rows = out_rows[1:]

    def key(row: List[str]) -> Tuple:
        vps_id = row[OUT_COLUMNS.index("VPS-ID")]
        ctx = ctx_by_vpsid.get(vps_id)
        if not ctx:
            return ("", 0, 0, 9999)
        return _sort_key_for_ctx(ctx)

    return [OUT_COLUMNS] + sorted(data_rows, key=key)


def _read_template_rows(csv_path: Path) -> List[Dict[str, str]]:
    """Read template puplookup.csv and normalize rows to OUT_COLUMNS shape."""
    if not csv_path.exists():
        raise DataValidationError(f"Missing template CSV: {csv_path}")

    normalized_rows: List[Dict[str, str]] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file_handle:
        reader = csv.reader(file_handle)
        header = next(reader, None)

        if not header:
            raise DataValidationError("Template CSV has no header row.")

        for row in reader:
            normalized = _normalize_template_row(header, row)
            if normalized:
                normalized_rows.append(normalized)

    return normalized_rows


def _read_vpsdb(vpsdb_path: Path) -> List[Dict[str, Any]]:
    """Read vpsdb.json as a list of game dicts."""
    if not vpsdb_path.exists():
        raise DataValidationError(f"Missing vpsdb.json: {vpsdb_path}")

    with vpsdb_path.open("r", encoding="utf-8") as file_handle:
        obj = json.load(file_handle)

    if not isinstance(obj, list):
        raise DataValidationError("vpsdb.json expected to be a JSON array.")

    return obj


def _write_csv(path: Path, rows: List[List[str]]) -> None:
    """Write output CSV with BOM to match site export."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8-sig", newline="") as file_handle:
        writer = csv.writer(file_handle, quoting=csv.QUOTE_MINIMAL)
        writer.writerows(rows)


@dataclass
class ExportService:
    """Generates the output CSV from cached data."""

    data_dir: Path
    output_dir: Path
    output_filename: str

    def generate_output_csv(self) -> Path:
        """Generate output CSV and return the created file path."""
        template_csv = self.data_dir / "puplookup.csv"
        vpsdb_json = self.data_dir / "vpsdb.json"

        template_rows = _read_template_rows(template_csv)
        vpsdb = _read_vpsdb(vpsdb_json)

        ctx_by_vpsid = _build_indexes(vpsdb)
        master_by_vpsid = _build_master_map(vpsdb)

        out_rows = _generate_rows(template_rows, ctx_by_vpsid, master_by_vpsid)

        out_path = self.output_dir / self.output_filename
        _write_csv(out_path, out_rows)

        log.info("Wrote output CSV: %s", out_path)
        return out_path