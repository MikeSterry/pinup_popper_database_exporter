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

# Columns match your current script.
BASE_COLUMNS = [
    "GameFileName","GameName","Manufact","GameYear","NumPlayers","GameType","Category",
    "GameTheme","WebLinkURL","IPDBNum","AltRunMode","DesignedBy","Author","GAMEVER","Rom","Tags","VPS-ID"
]
OUT_COLUMNS = [
    "GameFileName","GameName","Manufact","GameYear","NumPlayers","GameType","Category",
    "GameTheme","WebLinkURL","WebLink2URL","IPDBNum","AltRunMode","DesignedBy","Author","GAMEVER","Rom","Tags",
    "VPS-ID","WebGameID","MasterID"
]

YEAR_RE = re.compile(r"^\d{4}$")
VPS_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,}$")

WEBLINK2_BASE = "https://virtualpinballspreadsheet.github.io/tables"

def _norm_weblink(url: str) -> str:
    """Keep only IPDB links; drop placeholders and non-IPDB sources."""
    if not url:
        return ""
    u = url.strip()
    if u.lower() in {"not available","n/a","na","none"}:
        return ""
    if "ipdb.org" not in u.lower():
        return ""
    return u

def _parse_ipdb_num(ipdb_url: str) -> str:
    """Extract numeric machine id from an IPDB URL, if present."""
    if not ipdb_url:
        return ""
    m = re.search(r"(?:id=|machine\.cgi\?id=)(\d+)", ipdb_url)
    return m.group(1) if m else ""

def _excluded_feature(feature: str) -> bool:
    """Exclude noisy feature tags."""
    f = feature.strip()
    return (f.lower().startswith("incl.") or f == "no ROM")

def _weblink2(master_id: str, vps_id: str) -> str:
    """Build WebLink2URL as seen in the website export."""
    if not master_id or not vps_id:
        return ""
    return f"{WEBLINK2_BASE}?game={master_id}&fileType=tables&fileId={vps_id}"

def _sanitize_filename_part(s: str) -> str:
    """Mimic observed behavior (e.g., 50/50 -> 50_50)."""
    return s.replace("/", "_")

def _repair_template_row(row: List[str]) -> Optional[List[str]]:
    """Repair known malformations in GitHub puplookup.csv to ensure 17 base fields."""
    row = list(row)
    if len(row) < len(BASE_COLUMNS):
        return None

    # Case A: 18 columns because Manufact was split at a comma, and year shifted.
    if len(row) == len(BASE_COLUMNS) + 1:
        if (not YEAR_RE.match(row[3].strip())) and YEAR_RE.match(row[4].strip()):
            row[2] = f"{row[2].rstrip()}, {row[3].lstrip()}"
            del row[3]

    # Case B: more than expected columns: fold extras into Tags and keep last as VPS-ID.
    if len(row) > len(BASE_COLUMNS):
        extras = row[len(BASE_COLUMNS):]
        row = row[:len(BASE_COLUMNS)]
        cand = extras[-1].strip()
        if VPS_ID_RE.match(cand):
            shifted = row[15].strip()  # Tags
            if row[16].strip() and not VPS_ID_RE.match(row[16].strip()):
                shifted = (shifted + " " + row[16].strip()).strip() if shifted else row[16].strip()
            for tok in extras[:-1]:
                tok = tok.strip()
                if tok:
                    shifted = (shifted + " " + tok).strip() if shifted else tok
            row[15] = shifted
            row[16] = cand
        else:
            return None

    if len(row) != len(BASE_COLUMNS):
        return None
    if not VPS_ID_RE.match(row[16].strip()):
        return None
    return row

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
    for g in vpsdb:
        if not isinstance(g, dict):
            continue

        base_name = g.get("name") or ""
        manuf = g.get("manufacturer") or ""
        year = g.get("year")
        year_s = str(int(year)) if isinstance(year, (int, float)) and year is not None else (str(year) if year is not None else "")
        players = g.get("players")
        players_s = "" if players is None else (str(int(players)) if isinstance(players, (int, float)) else str(players))
        gtype = g.get("type") or ""
        theme = g.get("theme")
        theme_s = ", ".join(theme) if isinstance(theme, list) else (theme or "")
        designers = g.get("designers")
        designers_s = ", ".join(designers) if isinstance(designers, list) else ""
        ipdb_url = _norm_weblink(g.get("ipdbUrl") or "")
        ipdb_num = _parse_ipdb_num(ipdb_url)

        tfs = g.get("tableFiles") or []
        for idx, tf in enumerate(tfs):
            if not isinstance(tf, dict):
                continue
            vid = tf.get("id")
            if not vid:
                continue

            edition = tf.get("edition") or ""
            tf_gamefile_name = tf.get("gameFileName") or ""

            name_with_ed = base_name
            if edition and (edition.lower() not in base_name.lower()):
                name_with_ed = f"{base_name} - {edition}"

            game_name = f"{name_with_ed} ({manuf} {year_s})" if manuf and year_s else name_with_ed

            authors = tf.get("authors") or []
            if isinstance(authors, str):
                authors = [authors]
            authors = [a for a in authors if isinstance(a, str)]

            version = tf.get("version") or ""
            feats = tf.get("features") or []
            tags_list = [f for f in feats if isinstance(f, str) and f.strip() and not _excluded_feature(f)]

            created_at = tf.get("createdAt") or 0

            out[vid] = TableCtx(
                game_id=((tf.get("game") or {}).get("id") or g.get("id") or ""),
                game_name=game_name,
                manufacturer=manuf,
                year=year_s,
                players=players_s,
                game_type=gtype,
                theme=theme_s,
                designers=designers_s,
                ipdb_url=ipdb_url,
                ipdb_num=ipdb_num,
                authors=authors,
                version=version,
                tags_list=tags_list,
                edition=edition,
                created_at=int(created_at) if isinstance(created_at, (int, float)) else 0,
                tf_index=idx,
                tf_gamefile_name=tf_gamefile_name,
            )
    return out

def _build_master_map(vpsdb: List[Dict[str, Any]]) -> Dict[str, str]:
    """Map tableFiles[].id -> game.id (MasterID)."""
    out: Dict[str, str] = {}
    for g in vpsdb:
        if not isinstance(g, dict):
            continue
        gid = g.get("id") or ""
        for tf in (g.get("tableFiles") or []):
            if not isinstance(tf, dict):
                continue
            vid = tf.get("id")
            if not vid:
                continue
            tf_game = tf.get("game") or {}
            mid = (tf_game.get("id") if isinstance(tf_game, dict) else "") or gid
            out[vid] = mid
    return out

def _build_gamefile_name(ctx: TableCtx) -> str:
    """Reproduce website GameFileName behavior (prefers tableFiles[].gameFileName)."""
    if ctx.tf_gamefile_name:
        return ctx.tf_gamefile_name

    base = _sanitize_filename_part(ctx.game_name)

    author_part = ""
    if ctx.authors:
        author_part = ctx.authors[0]

    s = base
    if author_part:
        s = f"{s} {author_part} {ctx.version or ''}"
    else:
        if ctx.version:
            s = f"{s} {ctx.version}"

    if "MOD" in ctx.tags_list:
        s = f"{s} MOD"
    if "VR" in ctx.tags_list:
        s = f"{s} VR"
    return s

def _sort_key_for_ctx(ctx: TableCtx) -> Tuple:
    """Match site ordering: name prefix, createdAt desc, edition empty first, file order."""
    prefix = ctx.game_name.split(" (", 1)[0]
    return (prefix, -ctx.created_at, 0 if not ctx.edition else 1, ctx.tf_index)

def _generate_rows(template_rows: List[List[str]], ctx_by_vpsid: Dict[str, TableCtx], master_by_vpsid: Dict[str, str]) -> List[List[str]]:
    """Enrich and sort rows to match the site export."""
    out_rows: List[List[str]] = [OUT_COLUMNS]

    for trow in template_rows:
        vps_id = trow[BASE_COLUMNS.index("VPS-ID")]
        ctx = ctx_by_vpsid.get(vps_id)

        if not ctx:
            # Extend template row even if missing from vpsdb.json.
            master = ""
            wl2 = ""
            out = dict(zip(BASE_COLUMNS, trow))
            base_out = [out.get(c, "") for c in BASE_COLUMNS]
            wl_idx = BASE_COLUMNS.index("WebLinkURL")
            enriched = base_out[:wl_idx+1] + [wl2] + base_out[wl_idx+1:] + [vps_id, master]
            out_rows.append(enriched)
            continue

        master = master_by_vpsid.get(vps_id, ctx.game_id)
        wl2 = _weblink2(master, vps_id) if master else ""

        out = dict(zip(BASE_COLUMNS, trow))

        # Overwrite with vpsdb-derived truth.
        out["GameName"]   = ctx.game_name
        out["Manufact"]   = ctx.manufacturer
        out["GameYear"]   = ctx.year
        out["NumPlayers"] = ctx.players
        out["GameType"]   = ctx.game_type
        out["GameTheme"]  = ctx.theme
        out["WebLinkURL"] = ctx.ipdb_url
        out["IPDBNum"]    = ctx.ipdb_num
        out["DesignedBy"] = ctx.designers
        out["Author"]     = ", ".join(ctx.authors)
        out["GAMEVER"]    = ctx.version
        out["Tags"]       = ", ".join(ctx.tags_list)
        out["GameFileName"] = _build_gamefile_name(ctx)

        base_out = [out.get(c, "") for c in BASE_COLUMNS]
        wl_idx = BASE_COLUMNS.index("WebLinkURL")
        enriched = base_out[:wl_idx+1] + [wl2] + base_out[wl_idx+1:] + [vps_id, master]
        out_rows.append(enriched)

    # Sort (skip header row)
    data = out_rows[1:]

    def key(row: List[str]) -> Tuple:
        vid = row[OUT_COLUMNS.index("VPS-ID")]
        ctx = ctx_by_vpsid.get(vid)
        if not ctx:
            return ("", 0, 0, 9999)
        return _sort_key_for_ctx(ctx)

    return [OUT_COLUMNS] + sorted(data, key=key)

def _read_template_rows(csv_path: Path) -> List[List[str]]:
    """Read template puplookup.csv and repair malformed rows."""
    if not csv_path.exists():
        raise DataValidationError(f"Missing template CSV: {csv_path}")

    repaired: List[List[str]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            raise DataValidationError("Template CSV has no header row.")
        for row in reader:
            fixed = _repair_template_row(row)
            if fixed:
                repaired.append(fixed)
    return repaired

def _read_vpsdb(vpsdb_path: Path) -> List[Dict[str, Any]]:
    """Read vpsdb.json as a list of game dicts."""
    if not vpsdb_path.exists():
        raise DataValidationError(f"Missing vpsdb.json: {vpsdb_path}")
    with vpsdb_path.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, list):
        raise DataValidationError("vpsdb.json expected to be a JSON array.")
    return obj

def _write_csv(path: Path, rows: List[List[str]]) -> None:
    """Write output CSV with BOM to match site export."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerows(rows)

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
