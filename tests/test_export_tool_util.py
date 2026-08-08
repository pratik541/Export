from export_tool import _util
from export_tool import config


def test_is_blank_treats_none_empty_and_nan_string_as_blank():
    assert _util.is_blank(None)
    assert _util.is_blank("")
    assert _util.is_blank("   ")
    assert _util.is_blank("nan")
    assert not _util.is_blank("0")
    assert not _util.is_blank(0)


def test_safe_num_parses_numeric_strings_and_blanks_to_none():
    assert _util.safe_num("12.5") == 12.5
    assert _util.safe_num(7) == 7.0
    assert _util.safe_num(None) is None
    assert _util.safe_num("not a number") is None


def test_master_style_splits_on_slash():
    assert _util.master_style("STYLE1/2") == "STYLE1"
    assert _util.master_style("STYLE1") == "STYLE1"
    assert _util.master_style(None) is None


def test_fantasy_material_map_entries_have_the_expected_shape():
    assert len(config.FANTASY_MATERIAL_MAP) > 0
    for entry in config.FANTASY_MATERIAL_MAP:
        assert set(entry.keys()) == {"code", "c1", "suffix", "metal"}


def test_pack_column_headers_has_the_fields_the_fantasy_file_needs():
    required = {
        "sr", "sn", "cat", "kt", "qty", "gw", "tmw", "mv",
        "lab", "cert", "stud", "scc", "stnpcs", "stncts", "val", "making",
    }
    assert required.issubset(config.PACK_COLUMN_HEADERS.keys())


def test_jobsheet_columns_has_the_fields_the_fantasy_file_needs():
    assert set(config.JOBSHEET_COLUMNS.keys()) == {"design_no", "parent_style"}
