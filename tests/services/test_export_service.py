from pathlib import Path
import csv
import json

import pytest

from app.exceptions.custom_exceptions import DataValidationError
from app.services.export_service import (
    BASE_COLUMNS,
    OUT_COLUMNS,
    ExportService,
    TableCtx,
    _build_gamefile_name,
    _build_indexes,
    _build_master_map,
    _excluded_feature,
    _generate_rows,
    _normalize_template_row,
    _norm_weblink,
    _parse_ipdb_num,
    _read_template_rows,
    _read_vpsdb,
    _sanitize_filename_part,
    _sort_key_for_ctx,
    _weblink2,
)


def write_template_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def make_ctx(
    *,
    game_id: str = "game-1",
    game_name: str = "Attack From Mars (Bally 1995)",
    manufacturer: str = "Bally",
    year: str = "1995",
    players: str = "4",
    game_type: str = "SS",
    theme: str = "Aliens, Sci-Fi",
    designers: str = "Brian Eddy",
    ipdb_url: str = "https://www.ipdb.org/machine.cgi?id=3781",
    ipdb_num: str = "3781",
    authors: list[str] | None = None,
    version: str = "2.0",
    tags_list: list[str] | None = None,
    edition: str = "",
    created_at: int = 123456789,
    tf_index: int = 0,
    tf_gamefile_name: str = "",
) -> TableCtx:
    return TableCtx(
        game_id=game_id,
        game_name=game_name,
        manufacturer=manufacturer,
        year=year,
        players=players,
        game_type=game_type,
        theme=theme,
        designers=designers,
        ipdb_url=ipdb_url,
        ipdb_num=ipdb_num,
        authors=authors or ["Author A"],
        version=version,
        tags_list=tags_list or [],
        edition=edition,
        created_at=created_at,
        tf_index=tf_index,
        tf_gamefile_name=tf_gamefile_name,
    )


def test_norm_weblink_keeps_valid_ipdb_url():
    url = "https://www.ipdb.org/machine.cgi?id=1234"
    assert _norm_weblink(url) == url


def test_norm_weblink_drops_placeholder_and_non_ipdb_values():
    assert _norm_weblink("") == ""
    assert _norm_weblink("not available") == ""
    assert _norm_weblink("n/a") == ""
    assert _norm_weblink("https://example.com/foo") == ""


def test_parse_ipdb_num_extracts_id():
    assert _parse_ipdb_num("https://www.ipdb.org/machine.cgi?id=1234") == "1234"
    assert _parse_ipdb_num("https://www.ipdb.org/?id=5678") == "5678"
    assert _parse_ipdb_num("https://www.ipdb.org/") == ""
    assert _parse_ipdb_num("") == ""


def test_excluded_feature_filters_noise():
    assert _excluded_feature("Incl. topper")
    assert _excluded_feature("no ROM")
    assert not _excluded_feature("VR")
    assert not _excluded_feature("MOD")


def test_weblink2_builds_expected_url():
    assert (
        _weblink2("game-123", "file-456")
        == "https://virtualpinballspreadsheet.github.io/tables?game=game-123&fileType=tables&fileId=file-456"
    )
    assert _weblink2("", "file-456") == ""
    assert _weblink2("game-123", "") == ""


def test_sanitize_filename_part_replaces_forward_slash():
    assert _sanitize_filename_part("50/50") == "50_50"


def test_normalize_template_row_returns_none_for_invalid_vps_id():
    row = [""] * len(BASE_COLUMNS)
    row[BASE_COLUMNS.index("VPS-ID")] = "bad"
    assert _normalize_template_row(BASE_COLUMNS, row) is None


def test_normalize_template_row_repairs_split_manufacturer_in_legacy_row():
    row = [
        "file.vpx",
        "Game Name",
        "Bally",
        "Midway",
        "1992",
        "4",
        "SS",
        "Cat",
        "Theme",
        "https://www.ipdb.org/machine.cgi?id=1234",
        "1234",
        "",
        "Designer",
        "Author",
        "1.0",
        "rom1",
        "tag1",
        "ABCDEFGH",
    ]

    normalized = _normalize_template_row(BASE_COLUMNS, row)

    assert normalized is not None
    assert normalized["Manufact"] == "Bally, Midway"
    assert normalized["GameYear"] == "1992"
    assert normalized["VPS-ID"] == "ABCDEFGH"
    assert list(normalized.keys()) == OUT_COLUMNS


def test_normalize_template_row_folds_extra_legacy_columns_into_tags():
    row = [
        "file.vpx",
        "Game Name",
        "Williams",
        "1993",
        "4",
        "SS",
        "Cat",
        "Theme",
        "https://www.ipdb.org/machine.cgi?id=1234",
        "1234",
        "",
        "Designer",
        "Author",
        "1.0",
        "rom1",
        "tag1",
        "old-not-vps-id",
        "extra tag 1",
        "extra tag 2",
        "ABCDEFGH",
    ]

    normalized = _normalize_template_row(BASE_COLUMNS, row)

    assert normalized is not None
    assert normalized["Tags"] == "tag1 extra tag 1 extra tag 2"
    assert normalized["VPS-ID"] == "ABCDEFGH"


def test_normalize_template_row_keeps_modern_20_column_row_aligned():
    row = [
        "Attack From Mars (Bally 1995) Author A 2.0",
        "Attack From Mars (Bally 1995)",
        "Bally",
        "1995",
        "4",
        "SS",
        "",
        "Aliens, Sci-Fi",
        "https://www.ipdb.org/machine.cgi?id=3781",
        "https://virtualpinballspreadsheet.github.io/tables?game=game-1&fileType=tables&fileId=VPS12345",
        "3781",
        "",
        "Brian Eddy",
        "Author A",
        "2.0",
        "",
        "VR, MOD",
        "VPS12345",
        "game-1",
        "game-1",
    ]

    normalized = _normalize_template_row(OUT_COLUMNS, row)

    assert normalized is not None
    assert normalized["WebLink2URL"].endswith("fileId=VPS12345")
    assert normalized["IPDBNum"] == "3781"
    assert normalized["GAMEVER"] == "2.0"
    assert normalized["Tags"] == "VR, MOD"
    assert normalized["VPS-ID"] == "VPS12345"
    assert normalized["WebGameID"] == "game-1"
    assert normalized["MasterID"] == "game-1"


def test_read_template_rows_raises_when_file_missing(tmp_path):
    with pytest.raises(DataValidationError, match="Missing template CSV"):
        _read_template_rows(tmp_path / "puplookup.csv")


def test_read_template_rows_raises_when_header_missing(tmp_path):
    csv_path = tmp_path / "puplookup.csv"
    csv_path.write_text("", encoding="utf-8")

    with pytest.raises(DataValidationError, match="no header row"):
        _read_template_rows(csv_path)


def test_read_template_rows_skips_invalid_rows_and_keeps_valid_legacy_rows(tmp_path):
    csv_path = tmp_path / "puplookup.csv"

    valid_row = [
        "file.vpx",
        "Game Name",
        "Williams",
        "1993",
        "4",
        "SS",
        "Cat",
        "Theme",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "ABCDEFGH",
    ]
    invalid_row = ["too", "short"]

    write_template_csv(csv_path, BASE_COLUMNS, [valid_row, invalid_row])

    rows = _read_template_rows(csv_path)

    assert len(rows) == 1
    assert rows[0]["VPS-ID"] == "ABCDEFGH"
    assert rows[0]["GameName"] == "Game Name"


def test_read_template_rows_accepts_modern_20_column_template_rows(tmp_path):
    csv_path = tmp_path / "puplookup.csv"

    modern_row = [
        "Attack From Mars (Bally 1995) Author A 2.0",
        "Attack From Mars (Bally 1995)",
        "Bally",
        "1995",
        "4",
        "SS",
        "",
        "Aliens, Sci-Fi",
        "https://www.ipdb.org/machine.cgi?id=3781",
        "https://virtualpinballspreadsheet.github.io/tables?game=game-1&fileType=tables&fileId=VPS12345",
        "3781",
        "",
        "Brian Eddy",
        "Author A",
        "2.0",
        "",
        "VR, MOD",
        "VPS12345",
        "game-1",
        "game-1",
    ]

    write_template_csv(csv_path, OUT_COLUMNS, [modern_row])

    rows = _read_template_rows(csv_path)

    assert len(rows) == 1
    assert rows[0]["WebLink2URL"].endswith("fileId=VPS12345")
    assert rows[0]["IPDBNum"] == "3781"
    assert rows[0]["MasterID"] == "game-1"


def test_read_vpsdb_raises_when_file_missing(tmp_path):
    with pytest.raises(DataValidationError, match="Missing vpsdb.json"):
        _read_vpsdb(tmp_path / "vpsdb.json")


def test_read_vpsdb_raises_when_json_is_not_a_list(tmp_path):
    json_path = tmp_path / "vpsdb.json"
    json_path.write_text('{"not": "a list"}', encoding="utf-8")

    with pytest.raises(DataValidationError, match="JSON array"):
        _read_vpsdb(json_path)


def test_build_indexes_builds_context_from_vpsdb():
    vpsdb = [
        {
            "id": "game-1",
            "name": "Attack From Mars",
            "manufacturer": "Bally",
            "year": 1995,
            "players": 4,
            "type": "SS",
            "theme": ["Aliens", "Sci-Fi"],
            "designers": ["Brian Eddy"],
            "ipdbUrl": "https://www.ipdb.org/machine.cgi?id=3781",
            "tableFiles": [
                {
                    "id": "VPS12345",
                    "game": {"id": "game-1"},
                    "authors": ["Author A", "Author B"],
                    "version": "2.0",
                    "features": ["VR", "MOD", "no ROM", "Incl. topper"],
                    "edition": "Night Mod",
                    "createdAt": 123456789,
                    "gameFileName": "afm_night_mod.vpx",
                }
            ],
        }
    ]

    ctx_by_vpsid = _build_indexes(vpsdb)
    ctx = ctx_by_vpsid["VPS12345"]

    assert ctx.game_id == "game-1"
    assert ctx.game_name == "Attack From Mars - Night Mod (Bally 1995)"
    assert ctx.manufacturer == "Bally"
    assert ctx.year == "1995"
    assert ctx.players == "4"
    assert ctx.game_type == "SS"
    assert ctx.theme == "Aliens, Sci-Fi"
    assert ctx.designers == "Brian Eddy"
    assert ctx.ipdb_url == "https://www.ipdb.org/machine.cgi?id=3781"
    assert ctx.ipdb_num == "3781"
    assert ctx.authors == ["Author A", "Author B"]
    assert ctx.version == "2.0"
    assert ctx.tags_list == ["VR", "MOD"]
    assert ctx.edition == "Night Mod"
    assert ctx.created_at == 123456789
    assert ctx.tf_index == 0
    assert ctx.tf_gamefile_name == "afm_night_mod.vpx"


def test_build_master_map_prefers_nested_game_id_when_present():
    vpsdb = [
        {
            "id": "game-parent",
            "tableFiles": [
                {"id": "VPS12345", "game": {"id": "game-child"}},
                {"id": "VPS67890"},
            ],
        }
    ]

    master_map = _build_master_map(vpsdb)

    assert master_map["VPS12345"] == "game-child"
    assert master_map["VPS67890"] == "game-parent"


def test_build_gamefile_name_includes_author_and_version_when_raw_name_is_only_base_name():
    ctx = make_ctx(
        game_name="!WOW! (Mills Novelty Company 1932)",
        authors=["Druadic"],
        version="1.2b",
        tags_list=[],
        tf_gamefile_name="!WOW! (Mills Novelty Company 1932)",
    )

    assert _build_gamefile_name(ctx) == "!WOW! (Mills Novelty Company 1932) Druadic 1.2b"


def test_build_gamefile_name_appends_mod_tag():
    ctx = make_ctx(
        game_name="Some Table (Bally 1995)",
        authors=["Author A"],
        version="2.0",
        tags_list=["MOD"],
        tf_gamefile_name="Some Table (Bally 1995)",
    )

    assert _build_gamefile_name(ctx) == "Some Table (Bally 1995) Author A 2.0 MOD"


def test_build_gamefile_name_appends_vr_tag():
    ctx = make_ctx(
        game_name="Some Table (Bally 1995)",
        authors=["Author A"],
        version="2.0",
        tags_list=["VR"],
        tf_gamefile_name="Some Table (Bally 1995)",
    )

    assert _build_gamefile_name(ctx) == "Some Table (Bally 1995) Author A 2.0 VR"


def test_build_gamefile_name_appends_mod_and_vr_tags():
    ctx = make_ctx(
        game_name="Some Table (Bally 1995)",
        authors=["Author A"],
        version="2.0",
        tags_list=["VR", "MOD"],
        tf_gamefile_name="Some Table (Bally 1995)",
    )

    assert _build_gamefile_name(ctx) == "Some Table (Bally 1995) Author A 2.0 MOD VR"


def test_build_gamefile_name_uses_richer_raw_name_when_it_contains_version_data():
    ctx = make_ctx(
        game_name="Some Table (Bally 1995)",
        authors=["Author A"],
        version="2.0",
        tags_list=["VR"],
        tf_gamefile_name="Some Table (Bally 1995) Author A 2.0 VR",
    )

    assert _build_gamefile_name(ctx) == "Some Table (Bally 1995) Author A 2.0 VR"


def test_sort_key_for_ctx_orders_by_prefix_created_desc_edition_flag_then_index():
    ctx1 = make_ctx(game_name="Addams Family (Bally 1992)", created_at=200, edition="", tf_index=1)
    ctx2 = make_ctx(game_name="Addams Family (Bally 1992)", created_at=100, edition="Night Mod", tf_index=0)

    assert _sort_key_for_ctx(ctx1) < _sort_key_for_ctx(ctx2)


def test_generate_rows_enriches_gamefile_name_and_modern_columns():
    ctx = make_ctx(
        game_id="game-1",
        game_name="!WOW! (Mills Novelty Company 1932)",
        manufacturer="Mills Novelty Company",
        year="1932",
        authors=["Druadic"],
        version="1.2b",
        tags_list=["MOD", "VR"],
        ipdb_url="https://www.ipdb.org/machine.cgi?id=999",
        ipdb_num="999",
    )

    template_rows = [
        {
            "GameFileName": "!WOW! (Mills Novelty Company 1932)",
            "GameName": "!WOW! (Mills Novelty Company 1932)",
            "Manufact": "",
            "GameYear": "",
            "NumPlayers": "",
            "GameType": "",
            "Category": "",
            "GameTheme": "",
            "WebLinkURL": "",
            "WebLink2URL": "",
            "IPDBNum": "",
            "AltRunMode": "",
            "DesignedBy": "",
            "Author": "",
            "GAMEVER": "",
            "Rom": "",
            "Tags": "",
            "VPS-ID": "VPS12345",
            "WebGameID": "",
            "MasterID": "",
        }
    ]

    rows = _generate_rows(
        template_rows=template_rows,
        ctx_by_vpsid={"VPS12345": ctx},
        master_by_vpsid={"VPS12345": "game-1"},
    )

    assert rows[0] == OUT_COLUMNS
    data_row = rows[1]
    row_map = dict(zip(OUT_COLUMNS, data_row))

    assert row_map["GameFileName"] == "!WOW! (Mills Novelty Company 1932) Druadic 1.2b MOD VR"
    assert row_map["GameName"] == "!WOW! (Mills Novelty Company 1932)"
    assert row_map["Manufact"] == "Mills Novelty Company"
    assert row_map["GameYear"] == "1932"
    assert row_map["Author"] == "Druadic"
    assert row_map["GAMEVER"] == "1.2b"
    assert row_map["Tags"] == "MOD, VR"
    assert row_map["WebLink2URL"] == (
        "https://virtualpinballspreadsheet.github.io/tables?game=game-1&fileType=tables&fileId=VPS12345"
    )
    assert row_map["IPDBNum"] == "999"
    assert row_map["VPS-ID"] == "VPS12345"
    assert row_map["MasterID"] == "game-1"


def test_generate_rows_keeps_unmatched_template_row_aligned():
    template_rows = [
        {
            "GameFileName": "Legacy File",
            "GameName": "Legacy Game",
            "Manufact": "Bally",
            "GameYear": "1992",
            "NumPlayers": "4",
            "GameType": "SS",
            "Category": "",
            "GameTheme": "Theme",
            "WebLinkURL": "https://www.ipdb.org/machine.cgi?id=1234",
            "WebLink2URL": "",
            "IPDBNum": "1234",
            "AltRunMode": "",
            "DesignedBy": "Designer",
            "Author": "Author",
            "GAMEVER": "1.0",
            "Rom": "rom1",
            "Tags": "tag1",
            "VPS-ID": "ABCDEFGH",
            "WebGameID": "",
            "MasterID": "",
        }
    ]

    rows = _generate_rows(
        template_rows=template_rows,
        ctx_by_vpsid={},
        master_by_vpsid={},
    )

    assert rows[0] == OUT_COLUMNS
    data_row = rows[1]
    row_map = dict(zip(OUT_COLUMNS, data_row))

    assert row_map["GameFileName"] == "Legacy File"
    assert row_map["GameName"] == "Legacy Game"
    assert row_map["WebLink2URL"] == ""
    assert row_map["IPDBNum"] == "1234"
    assert row_map["VPS-ID"] == "ABCDEFGH"
    assert row_map["MasterID"] == ""


def test_export_service_generate_output_csv_writes_expected_file(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"

    template_row = [
        "!WOW! (Mills Novelty Company 1932)",
        "!WOW! (Mills Novelty Company 1932)",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "VPS12345",
    ]
    write_template_csv(data_dir / "puplookup.csv", BASE_COLUMNS, [template_row])

    vpsdb = [
        {
            "id": "game-1",
            "name": "!WOW!",
            "manufacturer": "Mills Novelty Company",
            "year": 1932,
            "players": 1,
            "type": "EM",
            "theme": ["Arcade"],
            "designers": ["Designer A"],
            "ipdbUrl": "https://www.ipdb.org/machine.cgi?id=999",
            "tableFiles": [
                {
                    "id": "VPS12345",
                    "game": {"id": "game-1"},
                    "authors": ["Druadic"],
                    "version": "1.2b",
                    "features": ["MOD", "VR"],
                    "edition": "",
                    "createdAt": 123456789,
                    "gameFileName": "!WOW! (Mills Novelty Company 1932)",
                }
            ],
        }
    ]
    write_json(data_dir / "vpsdb.json", vpsdb)

    service = ExportService(
        data_dir=data_dir,
        output_dir=output_dir,
        output_filename="puplookup.csv",
    )

    out_path = service.generate_output_csv()

    assert out_path.exists()

    with out_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    assert rows[0] == OUT_COLUMNS
    row_map = dict(zip(OUT_COLUMNS, rows[1]))
    assert row_map["GameFileName"] == "!WOW! (Mills Novelty Company 1932) Druadic 1.2b MOD VR"
    assert row_map["Author"] == "Druadic"
    assert row_map["GAMEVER"] == "1.2b"
    assert row_map["Tags"] == "MOD, VR"
    assert row_map["WebLink2URL"] == (
        "https://virtualpinballspreadsheet.github.io/tables?game=game-1&fileType=tables&fileId=VPS12345"
    )

def test_build_gamefile_name_uses_existing_template_base_name():
    ctx = make_ctx(
        game_name="The Addams Family (Bally 1992)",
        authors=["Cheese3075"],
        version="2.4.41",
        tags_list=["MOD"],
        tf_gamefile_name="The Addams Family (Bally 1992)",
    )

    result = _build_gamefile_name(
        ctx,
        existing_gamefile_name="Addams Family, The (Bally 1992)",
    )

    assert result == "Addams Family, The (Bally 1992) Cheese3075 2.4.41 MOD"

def test_build_gamefile_name_preserves_special_template_name():
    ctx = make_ctx(
        game_name="CastleStorm (Zen Studios 2015)",
        authors=["Zen Studios"],
        version="",
        tags_list=[],
        tf_gamefile_name="CastleStorm (Zen Studios 2015)",
    )

    result = _build_gamefile_name(
        ctx,
        existing_gamefile_name="Table 40",
    )

    assert result == "Table 40"

def test_build_gamefile_name_does_not_append_zen_studios_author():
    ctx = make_ctx(
        game_name="CastleStorm (Zen Studios 2015)",
        authors=["Zen Studios"],
        version="",
        tags_list=[],
    )

    result = _build_gamefile_name(
        ctx,
        existing_gamefile_name="Table 40",
    )

    assert result == "Table 40"

def test_build_gamefile_name_enriches_template_base_with_author_version_mod_vr():
    ctx = make_ctx(
        game_name="Some Table (Bally 1995)",
        authors=["Author A"],
        version="2.0",
        tags_list=["MOD", "VR"],
    )

    result = _build_gamefile_name(
        ctx,
        existing_gamefile_name="Some Table, The (Bally 1995)",
    )

    assert result == "Some Table, The (Bally 1995) Author A 2.0 MOD VR"

def test_build_gamefile_name_preserves_version_whitespace():
    ctx = make_ctx(
        game_name="Whoa Nellie! Big Juicy Melons (WhizBang Pinball 2011)",
        authors=["Popotte"],
        version=" FizX3.3 V1.00",
        tags_list=[],
    )

    result = _build_gamefile_name(
        ctx,
        existing_gamefile_name="Whoa Nellie! Big Juicy Melons (WhizBang Pinball 2011)",
    )

    assert result == "Whoa Nellie! Big Juicy Melons (WhizBang Pinball 2011) Popotte  FizX3.3 V1.00"