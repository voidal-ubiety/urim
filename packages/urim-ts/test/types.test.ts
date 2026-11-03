// Compile-time tests: checked by `npm run typecheck`. The runtime test only keeps node:test happy.
import { test } from "node:test";
import { defineDecision, noul, choice, score, threshold, createClient } from "../src/index.ts";
import { JEV, inputSchema } from "./fixtures.ts";

type Equal<A, B> = (<X>() => X extends A ? 1 : 2) extends (<X>() => X extends B ? 1 : 2) ? true : false;
const expectType = <T extends true>(_: T): void => undefined;

const def = defineDecision({
  contract: "t@1.0.0", tiers: [JEV], input: inputSchema,
  questions: { page: noul("p", { yes: "y", no: "n" }), team: choice("t", { a: "a", b: "b" }), sev: score("s", { lo: "l", hi: "h" }) },
  failover: { on: [] },
  thresholds: { gate: threshold({ on: "page" }) },
  interpret: ({ answers, cut }) => {
    expectType<Equal<typeof answers.page.value, "yes" | "no">>(true);
    expectType<Equal<typeof answers.team.value, "a" | "b">>(true);
    expectType<Equal<typeof answers.sev.value, "lo" | "hi">>(true);
    expectType<Equal<typeof cut.gate.passes, boolean>>(true);
    // @ts-expect-error unknown threshold name
    void cut.nope;
    // @ts-expect-error unknown question name
    void answers.nope;
    // @ts-expect-error label outside the space
    const bad: typeof answers.team.value = "c"; void bad;
    return { escalate: !cut.gate.passes, team: answers.team.value };
  },
});

async function typeOnly() {
  const r = await createClient({ adapters: [] }).decide(def, { report: "x" });
  if (r.ok) expectType<Equal<typeof r.value, { escalate: boolean; team: "a" | "b" }>>(true);
  const s = await createClient({ adapters: [] }).decideOrThrow(def, { report: "x" });
  expectType<Equal<typeof s.value, { escalate: boolean; team: "a" | "b" }>>(true);
  // @ts-expect-error input must match the schema type
  await createClient({ adapters: [] }).decide(def, { nope: 1 });
}
void typeOnly;

const noInterpret = defineDecision({ contract: "u@1.0.0", tiers: [JEV], input: inputSchema,
  questions: { page: noul("p", { yes: "y", no: "n" }) }, failover: { on: [] }, thresholds: {} });
async function defaultValue() {
  const s = await createClient({ adapters: [] }).decideOrThrow(noInterpret, { report: "x" });
  expectType<Equal<typeof s.value.page.value, "yes" | "no">>(true);
}
void defaultValue;

test("type tests compile (see npm run typecheck)", () => undefined);
