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
"""
from pathlib import Path

from rdflib import BNode, Graph, Namespace, RDF
from rdflib.plugins.serializers.turtle import TurtleSerializer
from rdflib import plugin

SHACL = Namespace('http://www.w3.org/ns/shacl#')
RML = Namespace('http://w3id.org/rml/')


class TurtleWithPrefixes(TurtleSerializer):
    """Always emits prefixes. Workaround for RDFLib#1048."""
    roundtrip_prefixes = True


plugin.register('tortoise', plugin.Serializer, 'merge_lib', 'TurtleWithPrefixes')


def merge_ttl_files(paths: list[Path]) -> Graph:
    """Parse and union every .ttl file in `paths` into one Graph, then
    rebuild any named extensible list into a standard RDF Collection."""
    merged = Graph()
    merged.bind('sh', SHACL)
    merged.bind('rml', RML)
    for p in paths:
        g = Graph()
        merged += g.parse(str(p), format='turtle')
    fix_extensible_lists(merged)
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


def write_ttl(graph: Graph, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=str(destination), format='tortoise')
