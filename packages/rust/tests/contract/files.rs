//! One test per contract ID in CONTRACT.md, driven by `fixtures/cases.json`.
use crate::support;

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
    c030_null_root => "C-030",
    c031_non_mapping_root => "C-031",
    c034_key_spelling => "C-034",
    c035_keys_distinct_by_type => "C-035",
    c040_hoshen_precedence => "C-040",
    c041_hoshen_not_int => "C-041",
    c042_hoshen_unsupported => "C-042",
    c043_urim_missing => "C-043",
    c045_lockfile_ok => "C-045",
    c046_lockfile_order => "C-046",
    c056_contract_ok => "C-056",
    c057_contract_order => "C-057",
    c060_not_urim => "C-060",
    c082_printable_only => "C-082",
    c083_depth_limit => "C-083",
    c084_no_anchors_aliases => "C-084",
    c085_no_tags => "C-085",
    c086_no_merge_keys => "C-086",
    c087_no_invisible_in_keys => "C-087",
    c088_no_invisible_in_identifiers => "C-088",
    c089_output_sanitized => "C-089",
    c090_first_violation_in_stream_order => "C-090",
    c091_prototype_keys_inert => "C-091",
    c092_identifiers_are_ascii => "C-092",
    c093_renamed_key_refused => "C-093",
    c094_hoshen_one_never_released => "C-094",
    c095_closed_schema => "C-095",
    c096_formats_and_bounds => "C-096",
    c097_contract_cross_rules => "C-097",
    c098_integrity => "C-098",
    c099_lockfile_cross_rules => "C-099",
    c100_urim_version_gate => "C-100",
}
