"""Central registry of executable, non-code pipeline node types."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NodeDefinition:
    key: str
    category: str
    min_inputs: int
    max_inputs: int


NODE_REGISTRY: dict[str, NodeDefinition] = {
    item.key: item
    for item in (
        NodeDefinition("source-dataset", "source", 0, 0),
        NodeDefinition("select-columns", "transform", 1, 1),
        NodeDefinition("rename-columns", "transform", 1, 1),
        NodeDefinition("filter", "transform", 1, 1),
        NodeDefinition("sort", "transform", 1, 1),
        NodeDefinition("join", "transform", 2, 2),
        NodeDefinition("union", "transform", 2, 20),
        NodeDefinition("aggregate", "transform", 1, 1),
        NodeDefinition("formula", "transform", 1, 1),
        NodeDefinition("type-convert", "transform", 1, 1),
        NodeDefinition("deduplicate", "transform", 1, 1),
        NodeDefinition("null-handling", "transform", 1, 1),
        NodeDefinition("output-dataset", "output", 1, 1),
        NodeDefinition("file-export", "output", 1, 1),
    )
}
