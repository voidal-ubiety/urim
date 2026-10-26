//! Character classes shared by the profile and by output sanitization.
//!
//! Implements: C-082, C-087, C-089

use std::borrow::Cow;
use std::fmt::Write as _;

/// YAML 1.2 `c-printable`: the only characters a document may contain (C-082).
pub(crate) const fn is_printable(c: char) -> bool {
    matches!(c, '\t' | '\n' | '\r' | ' '..='~' | '\u{85}' | '\u{a0}'..='\u{d7ff}' | '\u{e000}'..='\u{fffd}')
        || c >= '\u{10000}'
}

/// Invisible formatting and bidirectional-control characters, which are not allowed in
/// keys or identifiers (C-087, C-088) and are escaped in output (C-089).
pub(crate) const fn is_invisible(c: char) -> bool {
    matches!(
        c,
        '\u{ad}'
            | '\u{61c}'
            | '\u{180e}'
            | '\u{200b}'..='\u{200f}'
            | '\u{202a}'..='\u{202e}'
            | '\u{2060}'..='\u{2064}'
            | '\u{2066}'..='\u{206f}'
            | '\u{feff}'
            | '\u{fff9}'..='\u{fffb}'
            | '\u{e0000}'..='\u{e007f}'
    )
}

/// A character that must not reach a terminal unescaped: C0, DEL, C1 or invisible.
const fn is_unsafe_for_output(c: char) -> bool {
    matches!(c, '\0'..='\u{1f}' | '\u{7f}'..='\u{9f}') || is_invisible(c)
}

/// Escape every unsafe character as `\u{XXXX}` (uppercase hex, at least 4 digits) so a
/// path or document value cannot inject terminal escapes or reorder the line (C-089).
pub(crate) fn sanitize(s: &str) -> Cow<'_, str> {
    if !s.chars().any(is_unsafe_for_output) {
        return Cow::Borrowed(s);
    }
    let mut out = String::with_capacity(s.len().saturating_add(8));
    for c in s.chars() {
        if is_unsafe_for_output(c) {
            // Writing to a String cannot fail.
            let _ = write!(out, "\\u{{{:04X}}}", u32::from(c));
        } else {
            out.push(c);
        }
    }
    Cow::Owned(out)
}

/// Characters a Urim-profile document may contain: `c-printable` minus U+FEFF (only one leading
/// byte-order mark, stripped before this check) and minus NEL, LS and PS, which YAML 1.1 parsers
/// treat as line breaks but YAML 1.2 does not (C-082; resolves D-006 and D-007).
pub(crate) const fn is_profile_char(c: char) -> bool {
    is_printable(c) && !matches!(c, '\u{85}' | '\u{2028}' | '\u{2029}' | '\u{feff}')
}
