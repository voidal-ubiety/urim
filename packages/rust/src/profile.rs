//! The Urim YAML profile: text to a root mapping, rejecting everything the profile
//! forbids before any value is built.
//!
//! Rules, in the order they are applied:
//! 1. size limit (C-080), then profile characters only (`c-printable` without NEL, LS, PS or a
//!    non-leading U+FEFF) (C-082);
//! 2. well-formedness, in stream order: nesting deeper than the limit (C-083) is reported if
//!    it comes before the first syntax error, undefined alias or second document (C-020,
//!    C-022); those are `invalid YAML`. A parser's own nesting-limit error is `too deep`;
//! 3. profile violations over the complete event stream, first in stream order: an anchor or
//!    alias (C-084), a tag (C-085), a `<<` key (C-086), an invisible character in a key
//!    (C-087). When one node has both an anchor and a tag, the anchor is reported (C-090);
//! 4. value building: duplicate keys, collection keys and out-of-range integers are
//!    `invalid YAML` (C-021, C-023, C-024).
//!
//! The event pass keeps its own stack, so it never recurses: deep input cannot overflow
//! the native stack.
//!
//! Implements: C-014, C-020, C-021, C-022, C-023, C-080, C-082, C-083, C-084, C-085, C-086, C-087,
//! C-090

use saphyr_parser::{Event, Parser};
use serde_norway::{Mapping, Value};

use crate::Problem;
use crate::display::{is_invisible, is_profile_char};
use crate::limits::{MAX_BYTES, MAX_DEPTH};

/// Parse `text` as one Urim-profile YAML document whose root is a mapping.
pub(crate) fn parse_root(text: &str) -> Result<Mapping, Problem> {
    if text.len() > MAX_BYTES {
        return Err(Problem::TooLarge);
    }
    let text = text.strip_prefix('\u{feff}').unwrap_or(text);
    if !text.chars().all(is_profile_char) {
        return Err(Problem::InvalidYaml);
    }
    check_events(&well_formed(text)?)?;
    match serde_norway::from_str::<Value>(text) {
        Ok(v) if has_collection_key(&v) => Err(Problem::InvalidYaml),
        Ok(Value::Mapping(m)) => Ok(m),
        Ok(_) => Err(Problem::RootNotMapping),
        Err(_) => Err(Problem::InvalidYaml),
    }
}

/// One open collection in the event pass. `next_is_key` is only meaningful for mappings.
#[derive(Debug)]
struct Open {
    mapping: bool,
    next_is_key: bool,
}

/// Whether the node that starts now is a mapping key; advances the key/value toggle.
const fn starts_key(stack: &mut [Open]) -> bool {
    match stack.last_mut() {
        Some(open) if open.mapping => {
            let is_key = open.next_is_key;
            open.next_is_key = !is_key;
            is_key
        }
        _ => false,
    }
}

/// Anchors take precedence over tags on the same node.
const fn check_properties(anchor_id: usize, tagged: bool) -> Result<(), Problem> {
    if anchor_id != 0 {
        Err(Problem::AnchorOrAlias)
    } else if tagged {
        Err(Problem::Tag)
    } else {
        Ok(())
    }
}

/// saphyr-parser's message when its own flow-nesting limit (256 levels) is hit. That limit is
/// above `MAX_DEPTH`, so reaching it always means the input is too deep. Pinned with the parser
/// version (`=0.2.2`); `c083_depth_limit` fails if the wording changes.
const PARSER_DEPTH_ERROR: &str = "recursion limit exceeded";

/// Rule 2: parse the whole stream, stopping at the first depth or syntax problem.
fn well_formed(text: &str) -> Result<Vec<Event<'_>>, Problem> {
    let mut parser = Parser::new_from_str(text);
    let mut events = Vec::new();
    let mut depth = 0_usize;
    let mut documents = 0_u8;
    while let Some(next) = parser.next_event() {
        let (event, _span) = next.map_err(|e| {
            if e.info() == PARSER_DEPTH_ERROR || too_deep_before(text, e.marker().index()) {
                Problem::TooDeep
            } else {
                Problem::InvalidYaml
            }
        })?;
        match event {
            Event::DocumentStart(_) => {
                if documents > 0 {
                    return Err(Problem::InvalidYaml);
                }
                documents = 1;
            }
            Event::SequenceStart(..) | Event::MappingStart(..) => {
                if depth >= MAX_DEPTH {
                    return Err(Problem::TooDeep);
                }
                depth = depth.saturating_add(1);
            }
            Event::SequenceEnd | Event::MappingEnd => depth = depth.saturating_sub(1),
            _ => {}
        }
        events.push(event);
    }
    Ok(events)
}

/// The scanner looks ahead along a flow line and can fail on a later token before it hands over
/// the events of the collections opened in front of it. Re-parse only the text before the failing
/// token: if that already nests deeper than `MAX_DEPTH`, the depth came first in stream order
/// (C-090). `token_start` is a char index: saphyr counts chars despite its doc comment, which
/// the fixture `invalid/precedence-depth-before-syntax-multibyte.lock` pins.
fn too_deep_before(text: &str, token_start: usize) -> bool {
    let end = text.char_indices().nth(token_start).map_or(text.len(), |(at, _)| at);
    let mut parser = Parser::new_from_str(text.get(..end).unwrap_or_default());
    let mut depth = 0_usize;
    while let Some(Ok((event, _span))) = parser.next_event() {
        match event {
            Event::SequenceStart(..) | Event::MappingStart(..) => {
                if depth >= MAX_DEPTH {
                    return true;
                }
                depth = depth.saturating_add(1);
            }
            Event::SequenceEnd | Event::MappingEnd => depth = depth.saturating_sub(1),
            _ => {}
        }
    }
    false
}

/// Rule 3: profile violations over the complete event stream, first in stream order.
fn check_events(events: &[Event<'_>]) -> Result<(), Problem> {
    let mut stack: Vec<Open> = Vec::new();
    for event in events {
        match event {
            Event::Scalar(value, _style, anchor_id, tag) => {
                check_properties(*anchor_id, tag.is_some())?;
                if starts_key(&mut stack) {
                    if value == "<<" {
                        return Err(Problem::MergeKey);
                    }
                    if value.chars().any(is_invisible) {
                        return Err(Problem::InvisibleInKey);
                    }
                }
            }
            Event::SequenceStart(anchor_id, tag) | Event::MappingStart(anchor_id, tag) => {
                check_properties(*anchor_id, tag.is_some())?;
                starts_key(&mut stack);
                stack.push(Open { mapping: matches!(event, Event::MappingStart(..)), next_is_key: true });
            }
            Event::SequenceEnd | Event::MappingEnd => {
                stack.pop();
            }
            // An alias needs no case: `well_formed` rejects an undefined alias, and a defined
            // alias always follows its anchor, which `check_properties` reports first.
            Event::Alias(_)
            | Event::StreamStart
            | Event::StreamEnd
            | Event::DocumentStart(_)
            | Event::DocumentEnd
            | Event::Nothing => {}
        }
    }
    Ok(())
}

/// The value as an integer, if it is one (`1.0` is a float, not an integer).
pub(crate) fn as_int(v: &Value) -> Option<i128> {
    match v {
        Value::Number(n) => n.as_i64().map(i128::from).or_else(|| n.as_u64().map(i128::from)),
        _ => None,
    }
}

/// The value as a string, if it is one.
pub(crate) fn as_str(v: &Value) -> Option<&str> {
    match v {
        Value::String(s) => Some(s.as_str()),
        _ => None,
    }
}

const fn is_collection(v: &Value) -> bool {
    matches!(v, Value::Sequence(_) | Value::Mapping(_))
}

/// Mapping keys must be scalars. JS and Python cannot represent collection keys
/// faithfully, so every port rejects them (C-023). Tags never reach this point (C-085),
/// and depth is bounded by [`MAX_DEPTH`], so the recursion is bounded too.
fn has_collection_key(v: &Value) -> bool {
    match v {
        Value::Mapping(m) => m.iter().any(|(k, val)| is_collection(k) || has_collection_key(val)),
        Value::Sequence(s) => s.iter().any(has_collection_key),
        _ => false,
    }
}
