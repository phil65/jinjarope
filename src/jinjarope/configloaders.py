from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import jinja2

from jinjarope import envglobals, iterfilters, loaders, serializefilters, utils


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    import os

    type NestedMapping = Mapping[str, "str | NestedMapping"]


class NestedDictLoader(loaders.LoaderMixin, jinja2.BaseLoader):
    """A jinja loader for loading templates from nested dicts.

    This loader allows to access templates from nested dicts.
    Can be used to load templates defined with markup like TOML.

    Examples:
        ``` toml
        [example]
        template = "{{ something }}"
        ```
        ``` py
        content = tomllib.load(toml_file)
        loader = NestedDictLoader(content)
        env = Environment(loader=loader)
        env.get_template("example/template")
        ```
    """

    ID = "nested_dict"

    def __init__(self, mapping: NestedMapping) -> None:
        """Constructor.

        Args:
            mapping: A nested dict containing templates
        """
        super().__init__()
        self._data = mapping

    def __repr__(self) -> str:
        return utils.get_repr(self, mapping=self._data)

    def list_templates(self) -> list[str]:
        return list(iterfilters.flatten_dict(self._data).keys())

    def get_source(
        self,
        environment: jinja2.Environment,
        template: str,
    ) -> tuple[str, str | None, Callable[[], bool] | None]:
        data: Any = self._data
        try:
            for part in template.split("/"):
                data = data[part]
            assert isinstance(data, str)
        except (AssertionError, KeyError) as e:
            raise jinja2.TemplateNotFound(template) from e
        return data, None, lambda: True


class TemplateFileLoader(NestedDictLoader):
    """A jinja loader for loading templates from config files.

    This loader allows to access templates from config files.
    Config files often often resemble nested dicts when getting loaded / deserialized.

    The loader will load config file from given path and will make it accessible in the
    same way as the `NestedDictLoader`. (esp. TOML is well-suited for this)

    Config files can be loaded from any fsspec protocol URL.

    Examples:
        ``` py
        loader = TemplateFileLoader("http://path_to_toml_file.toml")
        env = Environment(loader=loader)
        env.get_template("example/template")
        ```
        ``` py
        loader = TemplateFileLoader("path/to/file.json")
        env = Environment(loader=loader)
        env.get_template("example/template")
        ```
    """

    ID = "template_file"

    def __init__(
        self,
        path: str | os.PathLike[str],
        fmt: Literal["toml", "json", "ini", "yaml"] | None = None,
        sub_path: tuple[str, ...] | None = None,
    ) -> None:
        """Constructor.

        Args:
            path: Path / fsspec protocol URL to the file
            fmt: Config file format. If None, try to auto-infer from file extension
            sub_path: An optional tuple of keys describing the "dictionary path" inside
                      the file
        """
        from upathtools import to_upath

        self.path = to_upath(path)
        text = envglobals.load_file_cached(self.path)
        file_fmt = fmt if fmt else self.path.suffix.lstrip(".")
        assert file_fmt in ["json", "toml", "yaml", "ini"]
        mapping = serializefilters.deserialize(text, fmt=file_fmt)  # type: ignore[arg-type]
        for part in sub_path or []:
            mapping = mapping[part]
        super().__init__(mapping=mapping)
        self._data = mapping

    def __repr__(self) -> str:
        path = self.path.as_posix()
        return utils.get_repr(self, path=path)


if __name__ == "__main__":
    from jinjarope import Environment

    env = Environment()
    env.loader = NestedDictLoader({"a": {"b": "c"}})
    text = env.render_template("a/b")
    print(text)
