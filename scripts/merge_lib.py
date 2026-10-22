"""
Shared helper for merging Turtle shape files into one graph.

Merging is a plain RDF triple union (rdflib Graph addition) -- the same
approach as the original rml-core/shapes_node/generate_shape.py.

The project uses a "named extensible list" convention so extension modules
can append alternatives without editing the base file: a named (non-blank)
list head like :nonConstantExpressionAlternativeList gets a real
rdf:first/rdf:rest chain in its defining module, and each extension module
just asserts one extra `:someList rdf:first X .` triple on that same
subject. TopBraid's SHACLListMembers treats rdf:first as non-functional and
happily collects every value, but that is not a valid RDF Collection per
spec -- an rdf:List node must have exactly one rdf:first and one rdf:rest --
so a standards-compliant SHACL engine walking the list the normal way would
only ever see one member and silently miss the rest. fix_extensible_lists()
rebuilds every such head, after merging, into one real chain (fresh blank
nodes, one rdf:first/rdf:rest per node, terminated in rdf:nil) containing
every contributed member, so the combined output works in any engine.

One of these named extensible lists backs an sh:alternativePath rather than
an sh:or/sh:in value set (:nonConstantPathAlternativeList in rml-core). The
W3C SHACL spec requires an alternativePath list to have at least two
members unconditionally -- there's no "until extended" exception -- so
until some module contributes a second alternative, that list has exactly
one member and is spec-invalid (pyshacl rejects it outright; our TopBraid
fork happens to tolerate it by silently degrading to the single path, but
that's a fork-specific leniency, not something to rely on).
collapse_singleton_alternative_paths() fixes this the other way: after
merging, any sh:alternativePath wrapper whose list has only one member is
replaced by that member directly -- a single "alternative" is just that
path (often itself a sequence), not a real disjunction -- so the generated
output stays valid SHACL regardless of which modules are combined.

blankify_lists() is an optional last step, off by default, for consumers
whose SHACL engine has a bug recognizing a list whose head is a named
(IRI) node -- it expects every rdf:List, including these named extensible
ones, to start at a blank node like ordinary Turtle `( ... )` sugar does.
It gives every such head a fresh blank node identity and rewrites every
triple that mentions it, once the list is already a normal chain and its
name no longer serves any purpose.
"""
from pathlib import Path

from rdflib import BNode, Graph, Namespace, RDF

SHACL = Namespace('http://www.w3.org/ns/shacl#')
RML = Namespace('http://w3id.org/rml/')


def merge_ttl_files(paths: list[Path], blankify: bool = False) -> Graph:
    """Parse and union every .ttl file in `paths` into one Graph, then
    rebuild any named extensible list into a standard RDF Collection, then
    collapse any sh:alternativePath list that ends up with only one member
    (e.g. core alone, before any module contributes a second alternative).
    If `blankify` is set, also give every remaining named list head a
    blank node identity (see blankify_lists)."""
    merged = Graph()
    merged.bind('sh', SHACL)
    merged.bind('rml', RML)
    for p in paths:
        g = Graph()
        merged += g.parse(str(p), format='turtle')
    fix_extensible_lists(merged)
    collapse_singleton_alternative_paths(merged)
    if blankify:
        blankify_lists(merged)
    return merged


def fix_extensible_lists(graph: Graph) -> None:
    """Rebuild every named (non-blank) rdf:List head in-place into one
    standard rdf:first/rdf:rest chain terminated by rdf:nil."""
    heads = {s for s in graph.subjects(RDF.first, None) if not isinstance(s, BNode)}

    for head in heads:
        members = sorted(graph.objects(head, RDF.first), key=str)

        # Walk the head's own pre-existing rdf:rest chain (the base
        # module's own tail, written as ordinary Turtle list sugar --
        # already a proper chain of anonymous blank nodes) to recover the
        # rest of its members.
        tail_nodes = set()
        node = next(graph.objects(head, RDF.rest), None)
        while node is not None and node != RDF.nil:
            if node in tail_nodes:
                break  # guard against a malformed cycle
            tail_nodes.add(node)
            v = next(graph.objects(node, RDF.first), None)
            if v is not None:
                members.append(v)
            node = next(graph.objects(node, RDF.rest), None)

        # Remove the old structure entirely.
        graph.remove((head, RDF.first, None))
        graph.remove((head, RDF.rest, None))
        for n in tail_nodes:
            graph.remove((n, RDF.first, None))
            graph.remove((n, RDF.rest, None))

        # Rebuild as one standard collection.
        if not members:
            graph.add((head, RDF.rest, RDF.nil))
            continue
        graph.add((head, RDF.first, members[0]))
        current = head
        for member in members[1:]:
            nxt = BNode()
            graph.add((current, RDF.rest, nxt))
            graph.add((nxt, RDF.first, member))
            current = nxt
        graph.add((current, RDF.rest, RDF.nil))


def _list_members(graph: Graph, head) -> list:
    """Walk a normal (already-fixed) rdf:first/rdf:rest chain starting at
    `head`, returning its members in order. `head` must already be a proper
    list -- call after fix_extensible_lists()."""
    members = []
    node = head
    while node is not None and node != RDF.nil:
        v = next(graph.objects(node, RDF.first), None)
        if v is not None:
            members.append(v)
        node = next(graph.objects(node, RDF.rest), None)
    return members


def _remove_list_triples(graph: Graph, head) -> None:
    node = head
    while node is not None and node != RDF.nil:
        nxt = next(graph.objects(node, RDF.rest), None)
        graph.remove((node, RDF.first, None))
        graph.remove((node, RDF.rest, None))
        graph.remove((node, RDF.type, RDF.List))
        node = nxt


def collapse_singleton_alternative_paths(graph: Graph) -> None:
    """The W3C SHACL spec requires an sh:alternativePath list to have at
    least two members (section 2.3.1.3) -- pyshacl enforces this strictly.
    But a module-extensible alternative-path list (see fix_extensible_lists)
    may legitimately have only one member until some other module
    contributes a second alternative (e.g. rml-core alone, or any
    combination where nothing yet extends that particular path). Rather
    than leave that invalid, collapse `[sh:alternativePath (onlyMember)]`
    down to just `onlyMember` wherever it's referenced -- a single
    "alternative" is just that path (often itself a sequence), not a real
    disjunction. Runs to a fixed point in case collapsing one wrapper
    exposes another (nested alternativePath-of-alternativePath)."""
    changed = True
    while changed:
        changed = False
        for wrapper in list(graph.subjects(SHACL.alternativePath, None)):
            head = next(graph.objects(wrapper, SHACL.alternativePath), None)
            if head is None:
                continue
            members = _list_members(graph, head)
            if len(members) != 1:
                continue
            only_member = members[0]

            for s, p in list(graph.subject_predicates(wrapper)):
                graph.remove((s, p, wrapper))
                graph.add((s, p, only_member))
            graph.remove((wrapper, SHACL.alternativePath, head))
            _remove_list_triples(graph, head)
            changed = True


def blankify_lists(graph: Graph) -> None:
    """Give every named (non-blank) rdf:List head a fresh blank node
    identity in-place, rewriting every triple that mentions it by name.
    Call this last, after fix_extensible_lists() and
    collapse_singleton_alternative_paths(), once every list is already a
    normal rdf:first/rdf:rest chain -- this only changes the head's
    identity, not the list's structure or members."""
    heads = [s for s in graph.subjects(RDF.type, RDF.List) if not isinstance(s, BNode)]
    for head in heads:
        blank = BNode()
        for s, p, o in list(graph.triples((head, None, None))):
            graph.remove((s, p, o))
            if (p, o) != (RDF.type, RDF.List):
                graph.add((blank, p, o))
        for s, p, o in list(graph.triples((None, None, head))):
            graph.remove((s, p, o))
            graph.add((s, p, blank))


def write_ttl(graph: Graph, destination: Path) -> None:
    """Write `graph` to `destination` as N-Triples, not Turtle. rdflib's
    TurtleSerializer has a bug where a blank-node list reachable from more
    than one place (exactly what blankify_lists() and the named
    extensible-list pattern both produce) sometimes loses content on the
    second occurrence, writing a bare `_:label` with nothing defining it.
    N-Triples has no collection/list sugar to get wrong -- every triple is
    written explicitly -- so it isn't exposed to that bug."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=str(destination), format='nt', encoding='utf-8')
