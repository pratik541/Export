from export_tool import materials


def test_exact_match_ignores_whitespace_and_case():
    result = materials.resolve_fantasy_material("18ktwg")
    assert result == materials.FantasyMaterial(c1="18KT WG", suffix="18KT WG", metal="18KT WG")


def test_concatenated_rose_gold_code_matches_the_spaced_table_entry():
    # Regression for the source tool's problem 4: a hardcoded shortcut used
    # to return "14KT RoseGold" (no space) for exactly this input, bypassing
    # the material table. The table-driven match always returns the table's
    # own (correctly spaced) text.
    result = materials.resolve_fantasy_material("14KTRG")
    assert result == materials.FantasyMaterial(c1="14KT RG", suffix="14KT RG", metal="14KT RG")


def test_unrecognized_code_falls_back_to_the_compacted_input():
    # Real-world case (Data/JNE016 sample): shipments use abbreviated KT
    # codes like "18KTY" that aren't in the table at all -- distinct from
    # the concatenated-but-fully-spelled-out case above. Falls back to the
    # code itself, unchanged (matching the source tool's own fallback).
    result = materials.resolve_fantasy_material("18KTY")
    assert result == materials.FantasyMaterial(c1="18KTY", suffix="18KTY", metal="18KTY")


def test_bare_rose_gold_abbreviation_without_full_word_still_resolves():
    # Real-world case (Data/JNE016 sample, 1 item): "14KTR" (no trailing G) must
    # still trigger the rose-gold special case, matching today's live tool.
    result = materials.resolve_fantasy_material("14KTR")
    assert result == materials.FantasyMaterial(c1="14KT RG", suffix="14KT RG", metal="14KT RG")


def test_spaceless_yellow_gold_abbreviation_stays_unmapped_matching_production():
    # Real-world case (Data/JNE016 sample, 9 items, ~20% of the file): "14KTY" is
    # NOT one of the two hardcoded special cases and does not exactly match any
    # table code (the table has "14KT Y" WITH a space) -- today's live tool ships
    # this unmapped, verbatim. A blanket both-sides-compacted match would
    # incorrectly map it to "14KT" and silently change real shipment output --
    # regression test for that exact bug.
    result = materials.resolve_fantasy_material("14KTY")
    assert result == materials.FantasyMaterial(c1="14KTY", suffix="14KTY", metal="14KTY")


def test_blank_kt_falls_back_to_empty_string():
    result = materials.resolve_fantasy_material(None)
    assert result == materials.FantasyMaterial(c1="", suffix="", metal="")


def test_build_item_name_strips_free_prefix():
    assert materials.build_item_name("FREE-AFDN1001", "AFDN1001", "14KT") == "AFDN1001-14KT"


def test_build_item_name_uses_master_style_when_parent_is_blank():
    assert materials.build_item_name(None, "AFDN1001", "14KT") == "AFDN1001-14KT"
    assert materials.build_item_name("nan", "AFDN1001", "14KT") == "AFDN1001-14KT"


def test_build_item_name_uses_master_style_when_parent_equals_master():
    assert materials.build_item_name("AFDN1001", "AFDN1001", "14KT") == "AFDN1001-14KT"


def test_build_item_name_uses_parent_when_alpha_prefixes_match():
    assert materials.build_item_name("AFDX55", "AFDX1001", "14KT") == "AFDX55-14KT"


def test_build_item_name_falls_back_to_master_when_alpha_prefixes_differ():
    assert materials.build_item_name("XYZ999", "AFDN1001", "14KT") == "AFDN1001-14KT"


def test_normalize_os_color_splits_two_letter_non_grade_color():
    assert materials.normalize_os_color("FG") == "F-G"


def test_normalize_os_color_leaves_known_grade_abbreviations_alone():
    assert materials.normalize_os_color("VS") == "VS"


def test_normalize_os_color_leaves_other_lengths_and_blanks_alone():
    assert materials.normalize_os_color("D") == "D"
    assert materials.normalize_os_color(None) is None
