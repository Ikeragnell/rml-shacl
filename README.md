# RML-SHACL

SHACL shapes for [RML](https://rml.io/) (RDF Mapping Language), designed to
be modular: one folder per RML specification module, combinable in any
subset so consumers can validate against exactly the modules they use.

## Modules

| Folder              | Validates                                                              |
|---------------------|------------------------------------------------------------------------|
| `rml-core`          | The RML Core vocabulary. Always required                               |
| `rml-cc`            | RML Collections & Container                                            |
| `rml-fnml`          | RML Functions                                                          |
| `rml-io`            | RML I/O                                                                |
| `rml-io-registry`   | The RML I/O reference-formulation registry                             |
| `rml-lv`            | RML Logical Views                                                      |

Each folder contains one or more `.ttl` files; every shape file in a folder
belongs to that module and can be combined freely with `rml-core` and any
subset of the other optional modules.

See [notice.md](notice.md) for provenance and licensing of each module's
shapes.

## Combining modules

`rml-core` is required; the optional modules can be mixed in freely because
some of the RDF lists that back a list-valued SHACL property (e.g. `sh:in`,
`sh:alternativePath`) are treated as containers rather than ordered lists:
their membership just needs to be the union of whatever each module
contributes, so a base module and any number of optional modules can each
add members independently, without knowing about each other or agreeing on
an order.

RDF and SHACL have no native container-list construct, so for this project
we hacked ordinary RDF lists into playing that role: a base module gives
the list a name instead of writing it as an anonymous `( ... )`, and an
optional module extends it by kind of inserting a member anywhere in the
list, in its own file. That's not a valid list on its own, so
`scripts/merge_lib.py` rebuilds it into a real, properly-formed list after
merging, so the combined output works in any conformant SHACL engine.

## Validation approach

Shapes target `rml:TriplesMap` only, not every RML class individually. From
there, `sh:node`/`sh:property` with `sh:path` drills down into subject
maps, predicate-object maps, term maps, and so on. Two reasons for that:

- A given problem lower in the structure would otherwise get reported once
  per class that happens to reach it, so targeting every class separately
  multiplies the same error instead of reporting it once.
- It keeps validation focused on mappings that actually produce triples.
  A construct that's declared but never wired into a triples map isn't
  reachable from `rml:TriplesMap`, so it's never targeted and never
  produces noise for something that was never going to run.


### Requirements

```
pip install rdflib
```

### Merge one module's files into one file

```
python scripts/merge_module.py rml-core
python scripts/merge_module.py rml-lv -o /some/other/path.ttl
```

Writes to `generated/modules/<module>.ttl` by default.

### Combine core with a chosen subset of modules

```
python scripts/combine_modules.py --modules cc fnml -o combined.ttl
```

Core alone:

```
python scripts/combine_modules.py -o core_only.ttl
```

### Generate every combination

```
python scripts/combine_modules.py --all
```

Writes all 2^5 = 32 combinations of `{cc, fnml, io, io-registry, lv}` on top
of core to `generated/combinations/`.

## Repository layout

```
rml-core/         RML Core shapes
rml-cc/           RML Collections & Containers shapes
rml-fnml/         RML Functions shapes
rml-io/           RML I/O shapes
rml-io-registry/  RML I/O reference-formulation registry shapes
rml-lv/           RML Logical Views shapes
scripts/          Merge/combine tooling (merge_lib.py, merge_module.py, combine_modules.py)
generated/        Build output (per-module and per-combination .ttl files)
notice.md         Provenance and licensing notes
```

`generated/` is build output, not hand-edited source; regenerate it with the
scripts above after changing any module's shapes.
