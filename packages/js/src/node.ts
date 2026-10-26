// Schema node types: the shape of the generated data in schema.gen.ts (same as schema.rs/node.py).
// Implements: C-095
import type { Fmt } from "./formats.js";

export interface Field {
  readonly name: string;
  readonly node: Node;
  readonly req: boolean;
}
export interface Tag {
  readonly field: string;
  readonly variants: readonly (readonly [string, readonly Field[]])[];
}
export type Pairs = readonly (readonly [string, string])[];
export type Leaf =
  | { readonly k: "str"; readonly fmt: Fmt; readonly desc: string }
  | { readonly k: "int"; readonly min: bigint | null; readonly desc: string }
  | {
      readonly k: "num";
      readonly min: number | null;
      readonly max: number | null;
      readonly minOpen: boolean;
      readonly maxOpen: boolean;
      readonly desc: string;
    }
  | { readonly k: "bool"; readonly desc: string }
  | { readonly k: "enum"; readonly values: readonly string[]; readonly desc: string }
  | {
      readonly k: "list";
      readonly items: Node;
      readonly min: number;
      readonly unique: boolean;
      readonly desc: string;
    }
  | {
      readonly k: "map";
      readonly key: Fmt;
      readonly value: Node;
      readonly min: number;
      readonly entries: readonly Field[];
      readonly desc: string;
    }
  | {
      readonly k: "obj";
      readonly fields: readonly Field[];
      readonly ext: boolean;
      readonly tag: Tag | null;
      readonly removed: Pairs;
      readonly desc: string;
    }
  | { readonly k: "one"; readonly keys: readonly Field[]; readonly forbid: Pairs; readonly desc: string }
  | { readonly k: "opaque"; readonly desc: string };
/** `alt` picks the first option that accepts the value's YAML kind; options never nest. */
export type Node = Leaf | { readonly k: "alt"; readonly options: readonly Leaf[]; readonly desc: string };
