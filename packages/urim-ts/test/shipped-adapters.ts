// Test helper: the provider factories `urim/adapters` ships, found by enumeration so tests
// never hard-code a vendor's name (only provider source may name a vendor).
import * as mod from "../src/adapters/index.ts";
import type { Adapter } from "../src/index.ts";

export const shippedAdapterNames: string[] = Object.keys(mod).filter((k) => k !== "httpAdapter");
export const shippedAdapters = (): Adapter[] =>
  shippedAdapterNames.map((k) => (mod as unknown as Record<string, () => Adapter>)[k]!());
