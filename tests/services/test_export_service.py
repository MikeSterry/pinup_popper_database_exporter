from pathlib import Path

import pytest

from app.exceptions.custom_exceptions import DataValidationError
from app.services.export_service import (
    BASE_COLUMNS,
    OUT_COLUMNS,
    ExportService,
    _build_gamefile_name,
    _build_indexes,
    _build_master_map,
    _excluded_feature,
    _generate_rows,
    _norm_weblink,
    _parse_ipdb_num,
    _read_template_rows,
    _read_vpsdb,
    _repair_template_row,
    _sanitize_filename_part,
    _sort_key_for_ctx,
    _weblink2,
)


def write_template_csv(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(",".join(BASE_COLUMNS) + "\n")
        for row in rows:
            escaped = []
            for value in row:
                value = "" if value is None else str(value)
                if "," in value or '"' in value:
                    value = '"' + value.replace('"', '""') + '"'
                escaped.append(value)
            f.write(",".join(escaped) + "\n")


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


def test_repair_template_row_returns_none_when_row_too_short():
    short_row = ["a"] * 5
    assert _repair_template_row(short_row) is None


def test_repair_template_row_repairs_split_manufacturer_column():
    row = [
        "file.vpx",                 # GameFileName
        "Game Name",                # GameName
        "Bally",                    # Manufact part 1
        "Midway",                   # Manufact part 2
        "1992",                     # GameYear
        "4",                        # NumPlayers
        "SS",                       # GameType
        "Cat",                      # Category
        "Theme",                    # GameTheme
        "https://www.ipdb.org/machine.cgi?id=1234",  # WebLinkURL
        "1234",                     # IPDBNum
        "",                         # AltRunMode
        "Designer",                 # DesignedBy
        "Author",                   # Author
        "1.0",                      # GAMEVER
        "rom1",                     # Rom
        "tag1",                     # Tags
        "ABCDEFGH",                 # VPS-ID
    ]

    repaired = _repair_template_row(row)

    assert repaired is not None
    assert len(repaired) == len(BASE_COLUMNS)
    assert repaired[2] == "Bally, Midway"
    assert repaired[3] == "1992"
    assert repaired[16] == "ABCDEFGH"


def test_repair_template_row_folds_extra_columns_into_tags_when_last_extra_is_vps_id():
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

    repaired = _repair_template_row(row)

    assert repaired is not None
    assert len(repaired) == len(BASE_COLUMNS)
    assert repaired[15] == "tag1 extra tag 1 extra tag 2"
    assert repaired[16] == "ABCDEFGH"


def test_repair_template_row_returns_none_when_final_vps_id_is_invalid():
    row = [
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
        "bad",
    ]
    assert _repair_template_row(row) is None


def test_read_template_rows_raises_when_file_missing(tmp_path):
    with pytest.raises(DataValidationError, match="Missing template CSV"):
        _read_template_rows(tmp_path / "puplookup.csv")


def test_read_template_rows_raises_when_header_missing(tmp_path):
    csv_path = tmp_path / "puplookup.csv"
    csv_path.write_text("", encoding="utf-8")

    with pytest.raises(DataValidationError, match="no header row"):
        _read_template_rows(csv_path)


def test_read_template_rows_skips_unrepairable_rows_and_keeps_valid_rows(tmp_path):
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

    write_template_csv(csv_path, [valid_row, invalid_row])

    rows = _read_template_rows(csv_path)

    assert rows == [valid_row]


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


def test_build_master_map_prefers_table_file_game_id_then_game_id():
    vpsdb = [
        {
            "id": "game-1",
            "tableFiles": [
                {"id": "VPS12345", "game": {"id": "master-1"}},
                {"id": "VPS67890"},
            ],
        }
    ]

    master_map = _build_master_map(vpsdb)

    assert master_map["VPS12345"] == "master-1"
    assert master_map["VPS67890"] == "game-1"


def test_build_gamefile_name_prefers_table_file_name():
    vpsdb = [
        {
            "id": "game-1",
            "name": "50/50",
            "manufacturer": "Bally",
            "year": 1990,
            "tableFiles": [
                {
                    "id": "VPS12345",
                    "authors": ["Author A"],
                    "version": "1.0",
                    "features": ["VR", "MOD"],
                    "gameFileName": "custom_name.vpx",
                }
            ],
        }
    ]

    ctx = _build_indexes(vpsdb)["VPS12345"]
    assert _build_gamefile_name(ctx) == "custom_name.vpx"


def test_build_gamefile_name_falls_back_to_generated_name():
    vpsdb = [
        {
            "id": "game-1",
            "name": "50/50",
            "manufacturer": "Bally",
            "year": 1990,
            "tableFiles": [
                {
                    "id": "VPS12345",
                    "authors": ["Author A"],
                    "version": "1.0",
                    "features": ["VR", "MOD"],
                    "gameFileName": "",
                }
            ],
        }
    ]

    ctx = _build_indexes(vpsdb)["VPS12345"]
    result = _build_gamefile_name(ctx)

    assert result == "50_50 (Bally 1990) Author A 1.0 MOD VR"


def test_sort_key_for_ctx_prefers_name_then_created_at_desc_then_empty_edition_then_index():
    vpsdb = [
        {
            "id": "game-1",
            "name": "Same Name",
            "manufacturer": "Bally",
            "year": 1990,
            "tableFiles": [
                {"id": "VPS11111", "createdAt": 200, "edition": "", "gameFileName": "a.vpx"},
                {"id": "VPS22222", "createdAt": 100, "edition": "Night", "gameFileName": "b.vpx"},
            ],
        }
    ]

    ctx_by_vpsid = _build_indexes(vpsdb)

    key1 = _sort_key_for_ctx(ctx_by_vpsid["VPS11111"])
    key2 = _sort_key_for_ctx(ctx_by_vpsid["VPS22222"])

    assert key1 < key2


def test_generate_rows_enriches_existing_vps_id_and_preserves_missing_vps_id():
    template_rows = [
        [
            "template_file_1.vpx",
            "Template Name 1",
            "Template Manuf",
            "1980",
            "2",
            "EM",
            "Cat",
            "Theme",
            "https://example.com/not-ipdb",
            "9999",
            "",
            "Template Designer",
            "Template Author",
            "0.1",
            "romx",
            "oldtag",
            "VPS12345",
        ],
        [
            "template_file_2.vpx",
            "Template Name 2",
            "Template Manuf",
            "1981",
            "4",
            "SS",
            "Cat2",
            "Theme2",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "oldtag2",
            "MISSING999",
        ],
    ]

    vpsdb = [
        {
            "id": "game-1",
            "name": "Attack From Mars",
            "manufacturer": "Bally",
            "year": 1995,
            "players": 4,
            "type": "SS",
            "theme": ["Aliens"],
            "designers": ["Brian Eddy"],
            "ipdbUrl": "https://www.ipdb.org/machine.cgi?id=3781",
            "tableFiles": [
                {
                    "id": "VPS12345",
                    "game": {"id": "master-1"},
                    "authors": ["Author A"],
                    "version": "2.0",
                    "features": ["VR"],
                    "edition": "",
                    "createdAt": 50,
                    "gameFileName": "afm.vpx",
                }
            ],
        }
    ]

    ctx_by_vpsid = _build_indexes(vpsdb)
    master_by_vpsid = _build_master_map(vpsdb)

    rows = _generate_rows(template_rows, ctx_by_vpsid, master_by_vpsid)

    assert rows[0] == OUT_COLUMNS
    assert len(rows) == 3

    enriched = next(row for row in rows[1:] if row[OUT_COLUMNS.index("VPS-ID")] == "VPS12345")
    missing = next(row for row in rows[1:] if row[OUT_COLUMNS.index("VPS-ID")] == "MISSING999")

    assert enriched[OUT_COLUMNS.index("GameName")] == "Attack From Mars (Bally 1995)"
    assert enriched[OUT_COLUMNS.index("Manufact")] == "Bally"
    assert enriched[OUT_COLUMNS.index("GameYear")] == "1995"
    assert enriched[OUT_COLUMNS.index("NumPlayers")] == "4"
    assert enriched[OUT_COLUMNS.index("GameType")] == "SS"
    assert enriched[OUT_COLUMNS.index("GameTheme")] == "Aliens"
    assert enriched[OUT_COLUMNS.index("WebLinkURL")] == "https://www.ipdb.org/machine.cgi?id=3781"
    assert enriched[OUT_COLUMNS.index("WebLink2URL")] == (
        "https://virtualpinballspreadsheet.github.io/tables?game=master-1&fileType=tables&fileId=VPS12345"
    )
    assert enriched[OUT_COLUMNS.index("IPDBNum")] == "3781"
    assert enriched[OUT_COLUMNS.index("DesignedBy")] == "Brian Eddy"
    assert enriched[OUT_COLUMNS.index("Author")] == "Author A"
    assert enriched[OUT_COLUMNS.index("GAMEVER")] == "2.0"
    assert enriched[OUT_COLUMNS.index("Tags")] == "VR"
    assert enriched[OUT_COLUMNS.index("GameFileName")] == "afm.vpx"
    assert enriched[OUT_COLUMNS.index("MasterID")] == "master-1"

    assert missing[OUT_COLUMNS.index("GameName")] == "Template Name 2"
    assert missing[OUT_COLUMNS.index("WebLink2URL")] == ""
    assert missing[OUT_COLUMNS.index("MasterID")] == ""


def test_generate_rows_sorts_using_context_key():
    template_rows = [
        [
            "x1.vpx", "Zeta", "M1", "1991", "4", "SS", "", "", "", "", "", "", "", "", "", "", "VPS11111"
        ],
        [
            "x2.vpx", "Alpha", "M2", "1992", "4", "SS", "", "", "", "", "", "", "", "", "", "", "VPS22222"
        ],
        [
            "x3.vpx", "Alpha", "M2", "1992", "4", "SS", "", "", "", "", "", "", "", "", "", "", "VPS33333"
        ],
    ]

    vpsdb = [
        {
            "id": "game-z",
            "name": "Zeta",
            "manufacturer": "Bally",
            "year": 1991,
            "tableFiles": [
                {"id": "VPS11111", "createdAt": 100, "edition": "", "gameFileName": "z.vpx"}
            ],
        },
        {
            "id": "game-a",
            "name": "Alpha",
            "manufacturer": "Williams",
            "year": 1992,
            "tableFiles": [
                {"id": "VPS22222", "createdAt": 200, "edition": "", "gameFileName": "a1.vpx"},
                {"id": "VPS33333", "createdAt": 100, "edition": "Night", "gameFileName": "a2.vpx"},
            ],
        },
    ]

    rows = _generate_rows(template_rows, _build_indexes(vpsdb), _build_master_map(vpsdb))
    data = rows[1:]

    assert [row[OUT_COLUMNS.index("VPS-ID")] for row in data] == ["VPS22222", "VPS33333", "VPS11111"]


def test_generate_output_csv_creates_expected_file_with_bom_and_enriched_content(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    output_dir.mkdir()

    write_template_csv(
        data_dir / "puplookup.csv",
        [
            [
                "template_file.vpx",
                "Template Name",
                "Template Manuf",
                "1980",
                "2",
                "EM",
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
                "VPS12345",
            ]
        ],
    )

    (data_dir / "vpsdb.json").write_text(
        """
        [
          {
            "id": "game-1",
            "name": "Attack From Mars",
            "manufacturer": "Bally",
            "year": 1995,
            "players": 4,
            "type": "SS",
            "theme": ["Aliens"],
            "designers": ["Brian Eddy"],
            "ipdbUrl": "https://www.ipdb.org/machine.cgi?id=3781",
            "tableFiles": [
              {
                "id": "VPS12345",
                "game": {"id": "master-1"},
                "authors": ["Author A"],
                "version": "2.0",
                "features": ["VR"],
                "edition": "",
                "createdAt": 50,
                "gameFileName": "afm.vpx"
              }
            ]
          }
        ]
        """.strip(),
        encoding="utf-8",
    )

    service = ExportService(
        data_dir=data_dir,
        output_dir=output_dir,
        output_filename="puplookup_out.csv",
    )

    out_path = service.generate_output_csv()

    assert out_path == output_dir / "puplookup_out.csv"
    assert out_path.exists()

    raw = out_path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")

    text = out_path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()

    assert lines[0].split(",") == OUT_COLUMNS
    assert "Attack From Mars (Bally 1995)" in text
    assert "https://www.ipdb.org/machine.cgi?id=3781" in text
    assert "https://virtualpinballspreadsheet.github.io/tables?game=master-1&fileType=tables&fileId=VPS12345" in text


def test_generate_output_csv_raises_when_template_missing(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    output_dir.mkdir()

    (data_dir / "vpsdb.json").write_text("[]", encoding="utf-8")

    service = ExportService(
        data_dir=data_dir,
        output_dir=output_dir,
        output_filename="puplookup_out.csv",
    )

    with pytest.raises(DataValidationError, match="Missing template CSV"):
        service.generate_output_csv()


def test_generate_output_csv_raises_when_vpsdb_missing(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    output_dir.mkdir()

    write_template_csv(
        data_dir / "puplookup.csv",
        [[
            "file.vpx", "Game", "Mfg", "1990", "4", "SS", "", "", "", "", "", "", "", "", "", "", "ABCDEFGH"
        ]],
    )

    service = ExportService(
        data_dir=data_dir,
        output_dir=output_dir,
        output_filename="puplookup_out.csv",
    )

    with pytest.raises(DataValidationError, match="Missing vpsdb.json"):
        service.generate_output_csv()