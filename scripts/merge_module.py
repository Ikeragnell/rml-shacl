#!/usr/bin/env python
"""
Merge every .ttl shape file in one module's folder into a single file.

Usage:
    python merge_module.py rml-core
    python merge_module.py rml-lv -o /some/other/path.ttl
"""
import argparse
import sys
from pathlib import Path

from merge_lib import merge_ttl_files, write_ttl

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('module', help='Module folder name, e.g. rml-core, rml-lv')
    p.add_argument('-o', '--output', type=Path, default=None,
                    help='Output file. Defaults to generated/modules/<module>.ttl')
    p.add_argument('-b', '--blank-lists', action='store_true',
                    help='Give named list heads a blank node identity instead, '
                         'for SHACL engines that mishandle a named rdf:List head')
    args = p.parse_args()

    module_dir = ROOT / args.module
    if not module_dir.is_dir():
        print(f'No such module folder: {module_dir}', file=sys.stderr)
        sys.exit(1)

    ttl_files = sorted(module_dir.glob('*.ttl'))
    if not ttl_files:
        print(f'No .ttl files found in {module_dir}', file=sys.stderr)
        sys.exit(1)

    destination = args.output or ROOT / 'generated' / 'modules' / f'{args.module}.ttl'

    print(f'Merging {len(ttl_files)} file(s) from {module_dir}:')
    for f in ttl_files:
        print(f'\t{f.name}')

    graph = merge_ttl_files(ttl_files, blankify=args.blank_lists)
    write_ttl(graph, destination)
    print(f'Wrote {len(graph)} triples to {destination}')


if __name__ == '__main__':
    main()
