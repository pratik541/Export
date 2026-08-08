from export_tool import materials


def test_exact_match_ignores_whitespace_and_case():
    result = materials.resolve_fantasy_material("18ktwg")
    assert result == materials.FantasyMaterial(c1="18KT WG", suffix="18KT WG", metal="18KT WG")


def test_bare_rose_gold_abbreviation_resolves_via_a_plain_table_row():
    # Real-world case (Data/JNE016 sample, 1 item), verified against the real
    # "Open Stock" reference file: "14KTR" resolves to "14KR" (c1=suffix=
    # metal), NOT "14KT RG" -- the source HTML file's hardcoded shortcut for
    # this exact input didn't match a single real "14KTR" row. "14KTR" is a
    # plain FANTASY_MATERIAL_MAP row now, not a special-case trigger.
    result = materials.resolve_fantasy_material("14KTR")
    assert result == materials.FantasyMaterial(c1="14KR", suffix="14KR", metal="14KR")


def test_concatenated_rose_gold_code_with_full_word_has_no_real_evidence_and_falls_back():
    # "14KTRG" (concatenated but fully spelled out, unlike bare "14KTR"
    # above) has no real-shipment evidence either way -- no special-case
    # trigger exists for it, so it falls back to the raw input verbatim,
    # same as any other code with no table match, flagged as unmatched.
    result = materials.resolve_fantasy_material("14KTRG")
    assert result == materials.FantasyMaterial(c1="14KTRG", suffix="14KTRG", metal="14KTRG", matched=False)


def test_yellow_gold_abbreviations_resolve_via_plain_table_rows():
    # Real-world case (Data/JNE016 sample, 10 items across 3 KT codes),
    # verified against the real "Open Stock" reference file: these compact
    # abbreviations all resolve to a matching short form (c1=suffix=metal),
    # not the source HTML file's default fallback-to-unmapped behavior.
    assert materials.resolve_fantasy_material("14KTY") == materials.FantasyMaterial(
        c1="14KY", suffix="14KY", metal="14KY"
    )
    assert materials.resolve_fantasy_material("18KTY") == materials.FantasyMaterial(
        c1="18KY", suffix="18KY", metal="18KY"
    )
    assert materials.resolve_fantasy_material("10KTY") == materials.FantasyMaterial(
        c1="10KY", suffix="10KY", metal="10KY"
    )


def test_ten_karat_rose_gold_abbreviation_resolves_via_a_plain_table_row():
    # Real-world case (Data/JNE013 sample), verified against that shipment's
    # real "Open Stock" reference file: same "strip the T" pattern as the
    # other compact abbreviations. Found via the "KT code not in
    # FANTASY_MATERIAL_MAP" warning in export_tool.fantasy_file.build_rows.
    result = materials.resolve_fantasy_material("10KTR")
    assert result == materials.FantasyMaterial(c1="10KR", suffix="10KR", metal="10KR")


def test_two_tone_abbreviation_has_no_real_evidence_and_stays_unmapped():
    # Real-world case (Data/JNE013 sample): unlike the single-color
    # abbreviations above, "18KT2T" (two-tone) was checked against that
    # shipment's real reference file and found to ship unmapped/verbatim in
    # production too -- no table row added, matching the real output.
    result = materials.resolve_fantasy_material("18KT2T")
    assert result == materials.FantasyMaterial(c1="18KT2T", suffix="18KT2T", metal="18KT2T", matched=False)


def test_unrecognized_code_falls_back_to_the_raw_input():
    # A KT code with no table row and no special-case trigger match falls
    # back to the raw (trimmed/uppercased) input, unchanged, flagged as
    # unmatched so callers can warn about it.
    result = materials.resolve_fantasy_material("22kt")
    assert result == materials.FantasyMaterial(c1="22KT", suffix="22KT", metal="22KT", matched=False)
    assert result.matched is False


def test_platinum_family_resolves_with_c1_and_metal_swapped_from_the_source_defaults():
    # Verified against the real "Open Stock" reference file: c1="PT",
    # suffix="PL", metal="PL" -- the source HTML file's defaults had
    # c1="PL", metal="PT" (swapped) for this same family of codes.
    for code in ("0.950", "0.95", "PT"):
        result = materials.resolve_fantasy_material(code)
        assert result == materials.FantasyMaterial(c1="PT", suffix="PL", metal="PL")


def test_blank_kt_falls_back_to_empty_string():
    result = materials.resolve_fantasy_material(None)
    assert result == materials.FantasyMaterial(c1="", suffix="", metal="", matched=False)


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
