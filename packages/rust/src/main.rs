//! The `urim` command-line tool: `urim check <file>`, `urim --version`, `urim --help`.

use std::ffi::OsString;
use std::io::{self, Write};
use std::process::ExitCode;

const USAGE: &str = "usage: urim check <file>";

/// Where a line of output goes.
#[derive(Debug, Clone, Copy)]
enum Stream {
    Out,
    Err,
}

/// Write one line. If the stream is closed (for example `urim check f | true`), the
/// line has no reader; the exit code still reports the result, so the error is
/// deliberately dropped instead of panicking the way `println!` does.
fn emit(stream: Stream, line: &str) {
    let written = match stream {
        Stream::Out => writeln!(io::stdout().lock(), "{line}"),
        Stream::Err => writeln!(io::stderr().lock(), "{line}"),
    };
    drop(written);
}

fn run(args: &[OsString]) -> (Stream, String, u8) {
    let flag = |names: [&str; 2]| matches!(args, [a] if names.iter().any(|n| a == n));
    if flag(["--version", "-V"]) {
        return (Stream::Out, format!("urim {}", urim::VERSION), 0);
    }
    if flag(["--help", "-h"]) {
        return (Stream::Out, USAGE.to_owned(), 0);
    }
    match args {
        [command, file] if command == "check" => {
            let result = urim::check_file(file);
            let stream = if result.is_ok() { Stream::Out } else { Stream::Err };
            let code = result.exit_code();
            (stream, result.into_line(), code)
        }
        _ => (Stream::Err, USAGE.to_owned(), 2),
    }
}

fn main() -> ExitCode {
    let args: Vec<OsString> = std::env::args_os().skip(1).collect();
    let (stream, line, code) = run(&args);
    emit(stream, &line);
    ExitCode::from(code)
}
