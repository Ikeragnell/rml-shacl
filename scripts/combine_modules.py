#!/usr/bin/env python
"""
Combine rml-core with a chosen subset of the optional modules into one
shapes file, or generate every combination at once.

rml-core is always included. The optional modules are rml-cc, rml-fnml,
rml-io, rml-io-registry, rml-lv -- 5 modules, so --all generates
2**5 = 32 combined files (rml-star is intentionally excluded: it has no
shapes_node content yet).

Usage:
    # One specific combination
    python combine_modules.py --modules cc fnml -o combined.ttl

    # Core alone
    python combine_modules.py -o core_only.ttl

    # All 32 combinations, written to generated/combinations/
    python combine_modules.py --all
"""
import argparse
import itertools
import sys
from pathlib import Path

from merge_lib import merge_ttl_files, write_ttl

ROOT = Path(__file__).resolve().parent.parent

CORE = 'rml-core'
OPTIONAL_MODULES = ['cc', 'fnml', 'io', 'io-registry', 'lv']  # canonical order
MODULE_DIR = {name: ROOT / f'rml-{name}' for name in OPTIONAL_MODULES}
MODULE_DIR['core'] = ROOT / CORE


def ttl_files_for(module_dirs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for d in module_dirs:
        if not d.is_dir():
            print(f'Warning: no such module folder: {d}', file=sys.stderr)
            continue
        files.extend(sorted(d.glob('*.ttl')))
    return files


def combo_name(selected: tuple[str, ...]) -> str:
    return 'core' if not selected else 'core+' + '+'.join(selected)


def build_one(selected: list[str], destination: Path) -> None:
    dirs = [MODULE_DIR['core']] + [MODULE_DIR[m] for m in selected]
    files = ttl_files_for(dirs)
    if not files:
        print(f'No .ttl files found for combination {selected}', file=sys.stderr)
        return
    graph = merge_ttl_files(files)
    write_ttl(graph, destination)
    print(f'{combo_name(tuple(selected)):40s} {len(files):3d} files  '
          f'{len(graph):5d} triples  -> {destination}')


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--modules', nargs='*', default=None, choices=OPTIONAL_MODULES,
                    metavar='MODULE',
                    help=f'Optional modules to include besides core. Choices: {OPTIONAL_MODULES}')
    p.add_argument('-o', '--output', type=Path, default=None,
                    help='Output file for a single combination. '
                         'Defaults to generated/combinations/<combo-name>.ttl')
    p.add_argument('--all', action='store_true',
                    help='Generate all 2^5 = 32 combinations of the optional modules')
    p.add_argument('--outdir', type=Path, default=ROOT / 'generated' / 'combinations',
                    help='Output directory when using --all')
    args = p.parse_args()

    if args.all:
        args.outdir.mkdir(parents=True, exist_ok=True)
        count = 0
        for r in range(len(OPTIONAL_MODULES) + 1):
            for combo in itertools.combinations(OPTIONAL_MODULES, r):
                destination = args.outdir / f'{combo_name(combo)}.ttl'
                build_one(list(combo), destination)
                count += 1
        print(f'\nGenerated {count} combinations in {args.outdir}')
        return

    selected = args.modules or []
    destination = args.output or (
        ROOT / 'generated' / 'combinations' / f'{combo_name(tuple(selected))}.ttl'
    )
    build_one(selected, destination)


if __name__ == '__main__':
    main()
