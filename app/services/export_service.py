"""Export service: generates CSV exports directly from local cached vpsdb.json
and matches VPS site export logic 1:1.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.exceptions.custom_exceptions import DataValidationError
from app.utils.logger import get_logger

log = get_logger(__name__)

INVALID_FILENAME_CHARS_RE = re.compile(r'[\\/:*?"<>|]')
WEBLINK2_BASE = "https://virtualpinballspreadsheet.github.io/tables"

EXCLUDED_TAGS = {
    "incl. B2S",
    "incl. ROM",
    "incl. Art",
    "incl. PuP",
    "incl. Video",
    "no ROM",
}

POPPER_COLUMNS = [
    "GameFileName","GameName","Manufact","GameYear","NumPlayers",
    "GameType","Category","GameTheme","WebLinkURL","WebLink2URL",
    "IPDBNum","AltRunMode","DesignedBy","Author","GAMEVER",
    "Rom","Tags","VPS-ID","WebGameID","MasterID",
]


@dataclass
class ExportService:
    data_dir: Path
    output_dir: Path
    output_filename: str

    def generate_output_csv(self) -> Path:
        vpsdb = _read_vpsdb(self.data_dir / "vpsdb.json")

        rows = list(_iter_table_files(vpsdb))

        # 🔥 CRITICAL: site sorts by ORIGINAL game.name
        rows.sort(key=lambda r: _str(r[0].get("name")).lower())

        popper_rows = [
            _build_popper_row(game, table)
            for game, table, _ in rows
        ]

        output_path = self.output_dir / self.output_filename
        _write_csv(output_path, POPPER_COLUMNS, popper_rows)

        return output_path


# -----------------------
# Core builders
# -----------------------

def _build_popper_row(game, table):
    game_id = _str(game.get("id"))
    table_id = _str(table.get("id"))
    ipdb_url = _norm_ipdb_url(game.get("ipdbUrl"))
    features = _as_list(table.get("features"))

    return {
        "GameFileName": _combined_game_file_name(game, table),
        "GameName": _combined_game_name(game, table),
        "Manufact": _str(game.get("manufacturer")),
        "GameYear": _str_year(game.get("year")),
        "NumPlayers": _str(game.get("players")),
        "GameType": _str(game.get("type")),
        "Category": "",
        "GameTheme": _join(game.get("theme")),
        "WebLinkURL": ipdb_url,
        "WebLink2URL": _vps_table_url(game_id, table_id),
        "IPDBNum": _parse_ipdb_num(ipdb_url),
        "AltRunMode": "",
        "DesignedBy": _join(game.get("designers")),
        "Author": _join(table.get("authors")),
        "GAMEVER": _str(table.get("version")),
        "Rom": _rom_version(game),
        "Tags": _export_tags(features),
        "VPS-ID": table_id,
        "WebGameID": table_id,
        "MasterID": game_id,
    }


# -----------------------
# Name logic (matches site)
# -----------------------

def _site_game_name(name: str) -> str:
    if name.lower().startswith("the "):
        return f"{name[4:].strip()}, The"
    return name


def _combined_game_name(game, table):
    name = _site_game_name(_str(game.get("name")))
    edition = _str(table.get("edition"))
    manufacturer = _str(game.get("manufacturer"))
    year = _str_year(game.get("year"))

    if edition:
        name = f"{name} - {edition}"

    return f"{name} ({manufacturer} {year})"


def _combined_game_file_name(game, table):
    existing = table.get("gameFileName")

    # 🔥 MUST use existing EXACTLY (no cleaning)
    if existing:
        return str(existing)

    name = _combined_game_name(game, table)
    authors = _as_list(table.get("authors"))
    version = _str(table.get("version"))
    features = _as_list(table.get("features"))

    value = name

    if authors:
        value += f" {authors[0]}"

    value += f" {version}"

    # 🔥 NOTE: SSF intentionally NOT included
    if _has_feature(features, "MOD"):
        value += " MOD"

    if _has_feature(features, "VR"):
        value += " VR"

    return _clean_filename(value)


# -----------------------
# Helpers
# -----------------------

def _rom_version(game):
    rom_files = game.get("romFiles") or []
    if not rom_files:
        return ""
    return _str(rom_files[0].get("version"))


def _norm_ipdb_url(value):
    url = _str(value)
    return url if ".ipdb.org/machine.cgi?id=" in url else ""


def _parse_ipdb_num(url):
    if ".ipdb.org/machine.cgi?id=" not in url:
        return ""
    return url.split(".cgi?id=", 1)[1]


def _export_tags(features):
    return ", ".join(f for f in features if f not in EXCLUDED_TAGS)


def _vps_table_url(game_id, table_id):
    return f"{WEBLINK2_BASE}?game={game_id}&fileType=tables&fileId={table_id}"


def _has_feature(features, name):
    return any(f.strip().upper() == name for f in features)


def _clean_filename(value):
    return INVALID_FILENAME_CHARS_RE.sub("_", value)


def _as_list(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if value:
        return [str(value).strip()]
    return []


def _join(value):
    return ", ".join(_as_list(value))


def _str(value):
    return "" if value is None else str(value).strip()


def _str_year(value):
    if isinstance(value, (int, float)):
        return str(int(value))
    return _str(value)


def _read_vpsdb(path):
    if not path.exists():
        raise DataValidationError("Missing vpsdb.json")

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise DataValidationError("vpsdb.json expected to be a JSON array.")

    return data


def _iter_table_files(vpsdb):
    for game in vpsdb:
        for idx, table in enumerate(game.get("tableFiles") or []):
            yield game, table, idx


def _write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)