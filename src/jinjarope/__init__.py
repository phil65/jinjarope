from importlib.metadata import version as _metadata_version

from .environment import BlockNotFoundError, Environment
from .envconfig import EnvConfig
from .loaders import (
    LoaderMixin,
    FileSystemLoader,
    ChoiceLoader,
    ModuleLoader,
    PackageLoader,
    FunctionLoader,
    PrefixLoader,
    DictLoader,
    from_json as get_loader_from_json,
)
from .rewriteloader import RewriteLoader
from .configloaders import NestedDictLoader, TemplateFileLoader
from .fsspecloaders import FsSpecFileSystemLoader, FsSpecProtocolPathLoader
from .loaderregistry import LoaderRegistry
from .jinjafile import JinjaFile, JinjaItem
from jinja2 import BaseLoader

registry = LoaderRegistry()

get_loader = registry.get_loader


def get_loader_cls_by_id(loader_id: str) -> type[BaseLoader]:
    from . import inspectfilters

    loaders = {i.ID: i for i in inspectfilters.list_subclasses(LoaderMixin) if "ID" in i.__dict__}
    return loaders[loader_id]  # type: ignore[no-any-return]


____version__ = _metadata_version("jinjarope")

__all__ = [
    "BlockNotFoundError",
    "ChoiceLoader",
    "DictLoader",
    "EnvConfig",
    "Environment",
    "FileSystemLoader",
    "FsSpecFileSystemLoader",
    "FsSpecProtocolPathLoader",
    "FunctionLoader",
    "JinjaFile",
    "JinjaItem",
    "ModuleLoader",
    "NestedDictLoader",
    "PackageLoader",
    "PrefixLoader",
    "RewriteLoader",
    "TemplateFileLoader",
    "get_loader",
    "get_loader_cls_by_id",
    "get_loader_from_json",
]
