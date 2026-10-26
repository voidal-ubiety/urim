//! Cross-field rules, run after the closed schema has passed (CONTRACT.md C-097, C-099).
//! Same order as `rules.ts`/`rules.py`. The schema has already fixed every shape, so the
//! accessors only distinguish present from absent (an absent key reads as null).
//!
//! Implements: C-097, C-099

use crate::Problem;
use crate::display::sanitize;
use crate::formats::is_num;
use crate::profile::as_str;
use crate::schema::{Seg, path_text};
use crate::schema_gen::{EMULATIONS, EXPERIMENTAL_QUESTION_TYPES};
use crate::value::Value;

fn text(value: &Value) -> String {
    sanitize(as_str(value).unwrap_or_default()).into_owned()
}

/// Whether `answer` is an answer of `question` (SPEC §5.4): an option key, yes/no, or a level index.
fn is_answer(question: &Value, answer: &str) -> bool {
    match as_str(question.get("type")) {
        Some("choice") => !question.get("options").get(answer).is_null(),
        Some("yesno") => answer == "yes" || answer == "no",
        Some("score") => is_num(answer) && !question.get("levels").get(answer).is_null(),
        _ => false,
    }
}

/// An extension's `fallback: {emulate: name}`: 0.2 registers no extension emulations.
fn extension_fallback(path: &[Seg<'_>], ext: &Value) -> Result<(), Problem> {
    let name = ext.get("fallback").get("emulate");
    if as_str(name).is_some() {
        let mut at = path.to_vec();
        at.extend([Seg::Key("fallback"), Seg::Key("emulate")]);
        return Err(Problem::NoEmulation { path: path_text(&at), name: text(name) });
    }
    Ok(())
}

fn question_types(root: &Value) -> Result<(), Problem> {
    for (name, question) in root.get("questions").entries() {
        let kind = as_str(question.get("type")).unwrap_or_default();
        let declaration = format!("question_types.{kind}");
        let undeclared = |_: &&&str| {
            root.get("requires").get(&declaration).is_null()
                && root.get("prefers").get(&declaration).is_null()
        };
        if let Some(experimental) =
            EXPERIMENTAL_QUESTION_TYPES.iter().find(|t| **t == kind).filter(undeclared)
        {
            return Err(Problem::UndeclaredExperimental {
                path: path_text(&[Seg::Key("questions"), Seg::Key(name), Seg::Key("type")]),
                kind: experimental,
            });
        }
    }
    Ok(())
}

fn policy(root: &Value) -> Result<(), Problem> {
    let questions = root.get("questions");
    for (id, rule) in root.get("policy").entries() {
        let asked = rule.get("question");
        let question = questions.get(as_str(asked).unwrap_or_default());
        if question.is_null() {
            let path = path_text(&[Seg::Key("policy"), Seg::Key(id), Seg::Key("question")]);
            return Err(Problem::UnknownQuestion { path, name: text(asked) });
        }
        if as_str(rule.get("when").get("answer")).is_some_and(|answer| !is_answer(question, answer)) {
            let path = path_text(&[Seg::Key("policy"), Seg::Key(id), Seg::Key("when"), Seg::Key("answer")]);
            return Err(Problem::NotAnAnswer { path, question: text(asked) });
        }
    }
    for (name, _) in root.get("eval").get("paraphrases").entries() {
        if questions.get(name).is_null() {
            let path = path_text(&[Seg::Key("eval"), Seg::Key("paraphrases"), Seg::Key(name)]);
            return Err(Problem::UnknownQuestion { path, name: sanitize(name).into_owned() });
        }
    }
    Ok(())
}

fn capabilities(root: &Value) -> Result<(), Problem> {
    let prefers = root.get("prefers");
    for (cap, _) in root.get("requires").entries() {
        if !prefers.get(cap).is_null() {
            return Err(Problem::AlsoPreferred(path_text(&[Seg::Key("requires"), Seg::Key(cap)])));
        }
    }
    for (cap, preference) in prefers.entries() {
        let name = preference.get("fallback").get("emulate");
        let registered = |e: &str| EMULATIONS.iter().any(|(c, names)| *c == cap && names.contains(&e));
        if as_str(name).is_some_and(|e| !registered(e)) {
            let path =
                path_text(&[Seg::Key("prefers"), Seg::Key(cap), Seg::Key("fallback"), Seg::Key("emulate")]);
            return Err(Problem::NoEmulation { path, name: text(name) });
        }
    }
    for (key, ext) in root.entries() {
        if key.starts_with("x-") {
            extension_fallback(&[Seg::Key(key)], ext)?;
        }
    }
    for (name, question) in root.get("questions").entries() {
        for (key, ext) in question.entries() {
            if key.starts_with("x-") {
                extension_fallback(&[Seg::Key("questions"), Seg::Key(name), Seg::Key(key)], ext)?;
            }
        }
    }
    Ok(())
}

/// The contract rules, in this order: question types, policy, eval, requires/prefers, emulations.
pub(crate) fn contract_rules(root: &Value) -> Result<(), Problem> {
    question_types(root)?;
    policy(root)?;
    capabilities(root)
}

/// The lockfile rules: each `active` and `standby` target is a key of `targets`.
pub(crate) fn lockfile_rules(root: &Value) -> Result<(), Problem> {
    for (id, entry) in root.get("contracts").entries() {
        let targets = entry.get("targets");
        let where_ = path_text(&[Seg::Key("contracts"), Seg::Key(id), Seg::Key("targets")]);
        let active = entry.get("active");
        if targets.get(as_str(active).unwrap_or_default()).is_null() {
            let path = path_text(&[Seg::Key("contracts"), Seg::Key(id), Seg::Key("active")]);
            return Err(Problem::NotATarget { path, value: text(active), targets: where_ });
        }
        for (i, (_, target)) in entry.get("standby").entries().into_iter().enumerate() {
            if targets.get(as_str(target).unwrap_or_default()).is_null() {
                let path =
                    path_text(&[Seg::Key("contracts"), Seg::Key(id), Seg::Key("standby"), Seg::Index(i)]);
                return Err(Problem::NotATarget { path, value: text(target), targets: where_ });
            }
        }
    }
    Ok(())
}
