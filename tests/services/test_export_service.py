import csv
import json
from pathlib import Path

import pytest

from app.exceptions.custom_exceptions import DataValidationError
from app.services.export_service import (
    POPPER_COLUMNS,
    ExportService,
    _combined_game_file_name,
    _combined_game_name,
    _export_tags,
    _norm_ipdb_url,
    _parse_ipdb_num,
    _read_vpsdb,
)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def sample_game(**overrides):
    game = {
        "id": "game-1",
        "name": "The Addams Family",
        "manufacturer": "Bally",
        "year": 1992,
        "players": 4,
        "type": "SS",
        "theme": ["Movie", "Fantasy"],
        "designers": ["Pat Lawlor"],
        "ipdbUrl": "https://www.ipdb.org/machine.cgi?id=20",
        "romFiles": [{"version": "taf_l7"}],
        "tableFiles": [
            {
                "id": "table-1",
                "authors": ["Author A"],
                "version": "2.0",
                "features": ["MOD", "VR", "SSF", "incl. B2S", "incl. nvram", "no ROM"],
                "edition": "",
                "gameFileName": "",
            }
        ],
    }
    game.update(overrides)
    return game


def test_read_vpsdb_raises_when_missing(tmp_path):
    with pytest.raises(DataValidationError, match="Missing vpsdb.json"):
        _read_vpsdb(tmp_path / "vpsdb.json")


def test_read_vpsdb_raises_when_not_array(tmp_path):
    path = tmp_path / "vpsdb.json"
    path.write_text('{"bad": true}', encoding="utf-8")

    with pytest.raises(DataValidationError, match="JSON array"):
        _read_vpsdb(path)


def test_combined_game_name_moves_the_to_end():
    game = sample_game()
    table = game["tableFiles"][0]

    assert _combined_game_name(game, table) == "Addams Family, The (Bally 1992)"


def test_combined_game_name_adds_edition():
    game = sample_game()
    table = game["tableFiles"][0]
    table["edition"] = "Gold Edition"

    assert _combined_game_name(game, table) == "Addams Family, The - Gold Edition (Bally 1992)"


def test_combined_game_file_name_builds_site_style_name_without_ssf():
    game = sample_game()
    table = game["tableFiles"][0]

    assert (
        _combined_game_file_name(game, table)
        == "Addams Family, The (Bally 1992) Author A 2.0 MOD VR"
    )


def test_combined_game_file_name_uses_existing_game_file_name_exactly():
    game = sample_game()
    table = game["tableFiles"][0]
    table["gameFileName"] = "Existing Name  With  Spaces"

    assert _combined_game_file_name(game, table) == "Existing Name  With  Spaces"


def test_export_tags_matches_site_filtering():
    features = [
        "MOD",
        "VR",
        "SSF",
        "incl. B2S",
        "incl. ROM",
        "incl. Art",
        "incl. PuP",
        "incl. Video",
        "incl. nvram",
        "no ROM",
    ]

    assert _export_tags(features) == "MOD, VR, SSF, incl. nvram"


def test_norm_ipdb_url_requires_machine_url():
    assert (
        _norm_ipdb_url("https://www.ipdb.org/machine.cgi?id=1234")
        == "https://www.ipdb.org/machine.cgi?id=1234"
    )
    assert _norm_ipdb_url("https://www.ipdb.org/?id=1234") == ""
    assert _norm_ipdb_url("https://example.com/foo") == ""


def test_parse_ipdb_num_matches_site_logic():
    assert _parse_ipdb_num("https://www.ipdb.org/machine.cgi?id=1234") == "1234"
    assert _parse_ipdb_num("https://www.ipdb.org/?id=1234") == ""
    assert _parse_ipdb_num("") == ""


def test_generate_output_csv_writes_expected_popper_csv(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"

    write_json(data_dir / "vpsdb.json", [sample_game()])

    service = ExportService(
        data_dir=data_dir,
        output_dir=output_dir,
        output_filename="puplookup.csv",
    )

    output_path = service.generate_output_csv()

    assert output_path == output_dir / "puplookup.csv"
    assert output_path.exists()

    with output_path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 1

    row = rows[0]

    assert list(row.keys()) == POPPER_COLUMNS
    assert row["GameFileName"] == "Addams Family, The (Bally 1992) Author A 2.0 MOD VR"
    assert row["GameName"] == "Addams Family, The (Bally 1992)"
    assert row["Manufact"] == "Bally"
    assert row["GameYear"] == "1992"
    assert row["NumPlayers"] == "4"
    assert row["GameType"] == "SS"
    assert row["GameTheme"] == "Movie, Fantasy"
    assert row["WebLinkURL"] == "https://www.ipdb.org/machine.cgi?id=20"
    assert row["WebLink2URL"] == (
        "https://virtualpinballspreadsheet.github.io/tables"
        "?game=game-1&fileType=tables&fileId=table-1"
    )
    assert row["IPDBNum"] == "20"
    assert row["DesignedBy"] == "Pat Lawlor"
    assert row["Author"] == "Author A"
    assert row["GAMEVER"] == "2.0"
    assert row["Rom"] == "taf_l7"
    assert row["Tags"] == "MOD, VR, SSF, incl. nvram"
    assert row["VPS-ID"] == "table-1"
    assert row["WebGameID"] == "table-1"
    assert row["MasterID"] == "game-1"


def test_generate_output_csv_sorts_by_original_game_name(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"

    b_game = sample_game(id="game-b", name="Z Game")
    b_game["tableFiles"][0]["id"] = "table-b"

    a_game = sample_game(id="game-a", name="A Game")
    a_game["tableFiles"][0]["id"] = "table-a"

    write_json(data_dir / "vpsdb.json", [b_game, a_game])

    service = ExportService(
        data_dir=data_dir,
        output_dir=output_dir,
        output_filename="puplookup.csv",
    )

    output_path = service.generate_output_csv()

    with output_path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    assert [row["MasterID"] for row in rows] == ["game-a", "game-b"]