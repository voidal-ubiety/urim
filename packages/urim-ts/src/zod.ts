// A barrier module ("urim/zod"): adapts Zod v4 to the internal SchemaAdapter (D9). The core never imports Zod.
// Verified against the installed zod 4.6.7: `z.toJSONSchema` is built in (no extra library).
import { z } from "zod";
import type { SchemaAdapter } from "./types.ts";

export const zodSchema = <S extends z.ZodType>(schema: S): SchemaAdapter<z.output<S>> => ({
  parse: (value) => {
    const r = schema.safeParse(value);
    return r.success ? { ok: true, value: r.data }
      : { ok: false, issues: r.error.issues.map((i) => ({ path: i.path.map(String).join("."), message: i.message })) };
  },
  toJSONSchema: () => z.toJSONSchema(schema),
});
