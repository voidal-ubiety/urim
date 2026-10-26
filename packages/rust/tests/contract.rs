//! One test per contract ID in CONTRACT.md, driven by `fixtures/cases.json`.
mod support;

macro_rules! file_contract {
    ($($name:ident => $id:literal),+ $(,)?) => {
        $(
            #[test]
            fn $name() {
                let cases = support::by_id("cases.json", $id);
                assert!(!cases.is_empty(), "no shared cases tagged {}", $id);
                for case in &cases {
                    support::assert_file_case(case, "exit", "output");
                }
            }
        )+

        /// The IDs above are exactly the IDs used in cases.json.
        #[test]
        fn c000_every_shared_case_id_has_a_rust_test() {
            let mut mine = vec![$($id.to_owned()),+];
            mine.sort();
            assert_eq!(mine, support::ids("cases.json"));
        }
    };
}

file_contract! {
    c010_missing_file => "C-010",
    c011_directory => "C-011",
    c013_not_utf8 => "C-013",
    c014_bom => "C-014",
    c015_crlf => "C-015",
    c020_syntax_error => "C-020",
    c021_duplicate_keys => "C-021",
    c022_single_document => "C-022",
    c023_collection_keys => "C-023",
    c024_int_range => "C-024",
    c025_core_schema_strings => "C-025",
    c026_int_forms => "C-026",
    c027_non_int_forms => "C-027",
    c028_floats => "C-028",
    c029_explicit_tags => "C-029",
    c030_null_root => "C-030",
    c031_non_mapping_root => "C-031",
    c032_anchors_aliases => "C-032",
    c033_no_merge_keys => "C-033",
    c034_key_spelling => "C-034",
    c035_keys_distinct_by_type => "C-035",
    c040_hoshen_precedence => "C-040",
    c041_hoshen_not_int => "C-041",
    c042_hoshen_unsupported => "C-042",
    c043_urim_missing => "C-043",
    c044_urim_not_string => "C-044",
    c045_lockfile_ok => "C-045",
    c046_lockfile_order => "C-046",
    c050_contract_both_keys => "C-050",
    c051_contract_key_type => "C-051",
    c052_contract_missing_keys => "C-052",
    c053_contract_string_fields => "C-053",
    c054_contract_state => "C-054",
    c055_contract_questions => "C-055",
    c056_contract_ok => "C-056",
    c057_contract_order => "C-057",
    c060_not_urim => "C-060",
}
