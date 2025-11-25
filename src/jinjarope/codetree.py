"""Analyzes and visualizes Python code structure as a tree representation.

This module provides functionality to parse Python source files and generate
a tree-like visualization of their structure, including classes, methods,
and functions with their decorators.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum, auto
import inspect
import os
from typing import TYPE_CHECKING

from upath.types import JoinablePath
from upathtools import to_upath


if TYPE_CHECKING:
    from jinjarope.utils import AnyPath


class NodeType(Enum):
    """Types of nodes found in Python code structure analysis.

    Each enum value represents a different structural element that can be
    found when parsing Python source code.
    """

    MODULE = auto()
    CLASS = auto()
    FUNCTION = auto()
    METHOD = auto()
    STATICMETHOD = auto()
    CLASSMETHOD = auto()
    PROPERTY = auto()
    ASYNC_FUNCTION = auto()
    ASYNC_METHOD = auto()


@dataclass
class Node:
    """Represents a node in the Python code structure tree.

    A node contains information about a specific code element (like a class
    or function) and maintains relationships with its child nodes.

    Args:
        name: The identifier of the code element
        type: The classification of the code element
        children: List of child nodes
        line_number: Source code line where this element appears
        decorators: List of decorator names applied to this element
    """

    name: str
    type: NodeType
    children: list[Node]
    line_number: int
    decorators: list[str]


@dataclass
class TreeOptions:
    """Configuration options for tree visualization.

    Controls the appearance and content of the generated tree structure.

    Args:
        show_types: Include node type annotations
        show_line_numbers: Display source line numbers
        show_decorators: Include decorator information
        sort_alphabetically: Sort nodes by name
        include_private: Include private members (_name)
        include_dunder: Include double underscore methods (__name__)
        max_depth: Maximum tree depth to display
        branch_style: Style of tree branches ("ascii" or "unicode")
    """

    show_types: bool = True
    show_line_numbers: bool = False
    show_decorators: bool = True
    sort_alphabetically: bool = False
    include_private: bool = True
    include_dunder: bool = False
    max_depth: int | None = None
    branch_style: str = "ascii"  # "ascii" or "unicode"

    @property
    def symbols(self) -> dict[str, str]:
        """Get tree drawing symbols based on selected style.

        Returns a dictionary containing the appropriate symbols for
        drawing tree branches.
        """
        if self.branch_style == "unicode":
            return {"pipe": "│   ", "last": "└── ", "branch": "├── ", "empty": "    "}
        return {"pipe": "|   ", "last": "`-- ", "branch": "|-- ", "empty": "    "}


def _get_decorator_names(decorators: list[ast.expr]) -> list[str]:
    """Extract decorator names from AST nodes."""
    names: list[str] = []
    for dec in decorators:
        if isinstance(dec, ast.Name):
            names.append(f"@{dec.id}")
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                names.append(f"@{dec.func.id}")
            elif isinstance(dec.func, ast.Attribute):
                names.append(f"@{dec.func.attr}")
    return names


def _should_include_node(name: str, options: TreeOptions) -> bool:
    """Determine if a node should be included based on options."""
    if name.startswith("__") and not options.include_dunder:
        return False
    return not (name.startswith("_") and not options.include_private)


def parse_object(obj: AnyPath | type) -> Node:
    """Parse Python source code into a tree structure.

    Analyzes the AST of a Python file and creates a hierarchical representation
    of its structure, including classes, methods, and functions.

    !!! note
        The parser recognizes special method types through decorators
        and handles both synchronous and asynchronous definitions.

    Args:
        obj: Path to the Python source file

    Example:
        ```python
        root = parse_object("example.py")
        print(f"Found {len(root.children)} top-level definitions")
        ```
    """
    if isinstance(obj, str | os.PathLike | JoinablePath):
        path = to_upath(obj)
        content = path.read_text("utf-8")
        name = path.name
    else:
        content = inspect.getsource(obj)
        name = obj.__name__
    tree = ast.parse(content)
    root = Node(name, NodeType.MODULE, [], 0, [])

    # Process top-level nodes
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            class_node = Node(
                node.name,
                NodeType.CLASS,
                [],
                node.lineno,
                _get_decorator_names(node.decorator_list),
            )
            root.children.append(class_node)

            # Process class body
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    decorators = _get_decorator_names(item.decorator_list)
                    node_type = NodeType.METHOD

                    # Determine method type based on decorators
                    if "@staticmethod" in decorators:
                        node_type = NodeType.STATICMETHOD
                    elif "@classmethod" in decorators:
                        node_type = NodeType.CLASSMETHOD
                    elif "@property" in decorators:
                        node_type = NodeType.PROPERTY
                    elif isinstance(item, ast.AsyncFunctionDef):
                        node_type = NodeType.ASYNC_METHOD
                    # mypy wants this check
                    assert isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
                    method_node = Node(item.name, node_type, [], item.lineno, decorators)
                    class_node.children.append(method_node)

        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            node_type = (
                NodeType.ASYNC_FUNCTION
                if isinstance(node, ast.AsyncFunctionDef)
                else NodeType.FUNCTION
            )
            func_node = Node(
                node.name,
                node_type,
                [],
                node.lineno,
                _get_decorator_names(node.decorator_list),
            )
            root.children.append(func_node)

    return root


def generate_tree(
    node: Node,
    options: TreeOptions,
    prefix: str = "",
    is_last: bool = True,
    depth: int = 0,
) -> str:
    """Recursively generate a textual tree representation from a Node.

    Traverses the provided Node structure and creates a string
    representing the tree in ASCII or Unicode format, applying
    the specified options to control its appearance.

    Args:
        node: The Node to start from
        options: Configuration options for tree visualization
        prefix: Prefix string to use for indentation
        is_last: Flag indicating if this node is the last child
        depth: Current depth in the tree

    !!! note
        This function is recursive and uses the provided options to
        determine if a node should be included and how it's formatted.

    Example:
        ```python
        root = parse_object("my_module.py")
        tree_str = generate_tree(root, options)
        print(tree_str)
        ```
    """
    if options.max_depth is not None and depth > options.max_depth:
        return ""

    if not _should_include_node(node.name, options):
        return ""

    symbols = options.symbols
    tree = prefix
    tree += symbols["last"] if is_last else symbols["branch"]

    # Build the node label
    label = node.name
    if options.show_types:
        label += f" ({node.type.name})"
    if options.show_line_numbers:
        label += f" [L{node.line_number}]"
    if options.show_decorators and node.decorators:
        label += f" [{', '.join(node.decorators)}]"

    tree += f"{label}\n"

    children = node.children
    if options.sort_alphabetically:
        children = sorted(children, key=lambda x: x.name)

    for i, child in enumerate(children):
        extension = symbols["empty"] if is_last else symbols["pipe"]
        tree += generate_tree(
            child,
            options,
            prefix + extension,
            i == len(children) - 1,
            depth + 1,
        )

    return tree


def get_structure_map(
    obj: os.PathLike[str] | str,
    *,
    show_types: bool = True,
    show_line_numbers: bool = False,
    show_decorators: bool = True,
    sort_alphabetically: bool = False,
    include_private: bool = True,
    include_dunder: bool = False,
    max_depth: int | None = None,
    use_unicode: bool = True,
) -> str:
    """Generate a textual tree representation of Python code structure.

    Creates a visual tree showing the hierarchical structure of classes,
    methods, and functions in a Python file, with customizable display options.

    !!! tip
        Use `use_unicode=True` for better-looking trees in terminals
        that support Unicode characters.

    Args:
        obj: Path to the Python source file or a Python object
        show_types: Include node type annotations
        show_line_numbers: Display source line numbers
        show_decorators: Include decorator information
        sort_alphabetically: Sort nodes by name
        include_private: Include private members
        include_dunder: Include double underscore methods
        max_depth: Maximum tree depth to display
        use_unicode: Use Unicode characters for tree branches

    Example:
        ```python
        tree = get_structure_map(
            "myfile.py",
            show_types=False,
            show_line_numbers=True,
            sort_alphabetically=True
        )
        print(tree)
        ```
    """
    options = TreeOptions(
        show_types=show_types,
        show_line_numbers=show_line_numbers,
        show_decorators=show_decorators,
        sort_alphabetically=sort_alphabetically,
        include_private=include_private,
        include_dunder=include_dunder,
        max_depth=max_depth,
        branch_style="unicode" if use_unicode else "ascii",
    )

    root = parse_object(obj)
    return generate_tree(root, options)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a tree representation of a Python file's structure"
    )
    parser.add_argument("file", help="Path to the Python file")
    parser.add_argument("--no-types", action="store_true", help="Don't show node types")
    parser.add_argument("--line-numbers", action="store_true", help="Show line numbers")
    parser.add_argument("--no-decorators", action="store_true", help="Don't show decorators")
    parser.add_argument("--sort", action="store_true", help="Sort nodes alphabetically")
    parser.add_argument("--no-private", action="store_true", help="Don't include private members")
    parser.add_argument("--dunder", action="store_true", help="Include dunder methods")
    parser.add_argument("--depth", type=int, help="Maximum depth to display")
    parser.add_argument(
        "--no-unicode", action="store_true", help="Use ASCII characters for the tree"
    )
    args = parser.parse_args()

    tree = get_structure_map(
        args.file,
        show_types=not args.no_types,
        show_line_numbers=args.line_numbers,
        show_decorators=not args.no_decorators,
        sort_alphabetically=args.sort,
        include_private=not args.no_private,
        include_dunder=args.dunder,
        max_depth=args.depth,
        use_unicode=not args.no_unicode,
    )

    print(tree)
    print(
        get_structure_map(
            "src/jinjarope/environment.py",
            show_types=False,
            show_line_numbers=True,
            show_decorators=True,
            sort_alphabetically=True,
            include_private=False,
            include_dunder=False,
            max_depth=2,
            use_unicode=True,
        )
    )
