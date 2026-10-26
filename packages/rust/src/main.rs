use std::process::ExitCode;

const USAGE: &str = "usage: urim check <file>";

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let args: Vec<&str> = args.iter().map(String::as_str).collect();
    match args.as_slice() {
        ["--version"] | ["-V"] => {
            println!("urim {}", urim::VERSION);
            ExitCode::SUCCESS
        }
        ["--help"] | ["-h"] => {
            println!("{USAGE}");
            ExitCode::SUCCESS
        }
        ["check", file] => {
            let result = urim::check_file(file);
            if result.ok {
                println!("{}", result.line);
                ExitCode::SUCCESS
            } else {
                eprintln!("{}", result.line);
                ExitCode::from(1)
            }
        }
        _ => {
            eprintln!("{USAGE}");
            ExitCode::from(2)
        }
    }
}
