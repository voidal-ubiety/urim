# Security policy

## Reporting a vulnerability

Report it privately through GitHub's private vulnerability reporting: on this repository, open the
**Security** tab and choose **Report a vulnerability**. Please don't open a public issue or pull
request for a vulnerability.

Include the affected package (`urim` on npm or PyPI), the version, and the smallest code or input that
reproduces the problem.

Fixes are best effort by a small volunteer team. There is no guaranteed response or fix time.

## Supported versions

| Version | Supported |
|---|---|
| 0.0.x (latest published) | Yes |
| anything older | No |

Urim is pre-1.0. Only the latest published 0.0.x release gets fixes.

## Scope: API keys and provider data

Urim calls model providers with keys that you supply. Both ports (`packages/urim-ts`, `packages/urim-py`)
work as follows:

- **No ambient credentials.** Urim never reads `process.env` or `os.environ` on its own. Keys come only
  from the `env` mapping you pass to the client (TypeScript `createClient({ env })`, Python
  `create_client(env=...)`). It is empty by default. Passing your process environment is your choice.
- **Keys are only sent to the provider.** A key is read when the request is sent and goes only into that
  provider's auth header. Urim doesn't log keys or put them in errors or attempt records. Tests check
  this in both ports, including the console and log output when a provider returns an auth error.
- **Raw bodies are opt-in.** A provider's raw response body is attached to a result only when you set
  `raw` (on the client or per call). It is off by default. A raw body is the provider's own data, so
  treat it like any other model output.
- **Logging.** The only thing Urim logs is a one-time warning when your `onSettled` / `on_settled`
  hook throws. That warning contains your hook's error message.
- **No runtime dependencies.** Neither package has required runtime dependencies. Zod (TypeScript) and
  pydantic/httpx (Python) are optional. npm installs in CI run with `--ignore-scripts`.

Out of scope: the security of the providers themselves, keys that your own code leaks (for example by
logging the `env` you pass in or by putting secrets into hook errors), and the content of model answers.
