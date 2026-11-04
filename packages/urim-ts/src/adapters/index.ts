// A: real HTTP adapters (opt-in: `import { typesafeJev, openaiDecisions } from "@voidal-ubiety/urim/adapters"`).
// Nothing here runs unless you import it AND pass it to createClient. The credential arrives from the client,
// which reads the env var named by `credentialEnv` at send time. It is put in one request header and never
// logged, stored, or placed in any error message. fetch is injected (ClientDeps.fetch) so tests use a mock.
import { DESCRIPTORS, type Descriptor } from "../descriptors.ts";
import { UrimError } from "../errors.ts";
import type { Adapter } from "../testing.ts";
import type { WireReply } from "../types.ts";

const headersOf = (h: Headers): Record<string, string> => {
  const out: Record<string, string> = {};
  h.forEach((value, key) => { out[key.toLowerCase()] = value; });
  return out;
};

const readBody = async (res: Response): Promise<unknown> => {
  const text = await res.text();
  try { return JSON.parse(text) as unknown; } catch { return text; } // non-JSON -> decoder reports nonconformant
};

/** One adapter per descriptor whose URL needs no caller-supplied placeholders. */
export const httpAdapter = (d: Descriptor): Adapter => {
  const auth = d.auth[0];
  if (auth === undefined || d.url.includes("{")) {
    throw new UrimError("invalid_definition", `${d.provider}: descriptor needs URL/auth options this slice does not support`);
  }
  return Object.freeze({
    provider: d.provider,
    credentialEnv: auth.env,
    async send(req, io): Promise<WireReply> {
      if (io.credential === "") {
        throw new UrimError("auth", `missing credential: set ${auth.env}`, { tier: req.tierId });
      }
      const started = Date.now();
      const res = await io.fetch(req.url, {
        method: "POST",
        headers: { "content-type": "application/json",
          [auth.header]: auth.scheme === null ? io.credential : `${auth.scheme} ${io.credential}` },
        body: JSON.stringify(req.body),
        signal: io.signal,
      });
      return { status: res.status, headers: headersOf(res.headers), body: await readBody(res), latencyMs: Date.now() - started };
    },
  });
};

/** TypeSafe Jev, systemone camp. Bearer TYPESAFE_API_KEY -> https://api.typesafe.ai/v1/systemone */
export const typesafeJev = (): Adapter => httpAdapter(DESCRIPTORS["typesafe"]!);
/** OpenAI, decisions camp. Bearer OPENAI_API_KEY -> https://api.openai.com/v1/decisions */
export const openaiDecisions = (): Adapter => httpAdapter(DESCRIPTORS["openai"]!);
