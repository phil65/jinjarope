# AGENTS.md

## Overview

jinjarope is a Jinja2 toolkit: an enhanced `jinja2.Environment` subclass with ~150 extra
filters/tests/globals, loader subclasses (incl. fsspec-based remote loaders), "JinjaFiles"
(TOML files declaring filters/tests/functions/config), custom tag extensions and an fsspec
filesystem view of a loader. It is a core dependency of mknodes, docler, toolreg and others:
treat the public API (`jinjarope/__init__.py`, filter names in `resources/*.toml`,
`Environment` methods) as stable.

## Architecture

- `src/jinjarope/environment.py`: `Environment(jinja2.Environment)`. `__init__` loads the
  JinjaFiles in `resources/` (`filters.toml`, `tests.toml`, `functions.toml`,
  `humanize_filters.toml`, `llm_filters.toml`), adds `envglobals.ENV_GLOBALS`, then calls
  every `jinjarope.environment` entry point (`utils.entry_points`, via epregistry) with the env.
  Also: `render_string/render_file/render_template`, `evaluate`, `render_block`,
  `with_globals`, `set_undefined`, `load_jinja_file`.
- `src/jinjarope/jinjafile.py`: `JinjaFile` (parses a TOML file) and `JinjaItem` (one
  filter/test/function; `fn` is a dotted import path resolved lazily, `required_packages`,
  `examples`, `aliases`, `group`, `icon`).
- `src/jinjarope/resources/*.toml`: the declarations of all built-in filters/tests/functions.
  Their implementations live in `*filters.py`, `envtests.py`, `envglobals.py` or third-party
  packages (string paths, so optional packages are only imported when used).
- Loaders: `loaders.py` (`LoaderMixin` adds `|` -> ChoiceLoader, `"prefix" / loader` ->
  PrefixLoader, `loader[path]`, `in`; subclasses of all jinja2 loaders, `from_json`),
  `fsspecloaders.py` (`FsSpecFileSystemLoader`, `FsSpecProtocolPathLoader`),
  `configloaders.py` (`NestedDictLoader`, `TemplateFileLoader`), `rewriteloader.py`,
  `loaderregistry.py` (`LoaderRegistry`, exposed as `jinjarope.get_loader`).
- `jinjaloaderfilesystem.py`: read-only fsspec filesystem over an env's loader.
- `envconfig.py` (`EnvConfig` dataclass), `undefined.py` (undefined behaviors incl. `lax`),
  `localization.py` (babel-based i18n, optional), `tags.py` (base classes for custom tags),
  `decorators.py`, `deepmerge.py`, `filetree.py`, `codetree.py`, `icons.py`/`iconfilters.py`
  (`resources/icons.json.gzip` index, pycons).
- `cli.py`: typer app (`jinjarope -i TEMPLATE [-j JINJAFILE] [-o OUTPUT]`), needs the `cli` extra.
- `manual.py`: mknodes `build_fn` for the docs site (referenced in `mkdocs.yml`); imports
  mknodes, which is not a runtime dependency. Never import it from package code.

## Where to look

| Task | Location |
| --- | --- |
| Add/change a built-in filter/test/function | implementation in `src/jinjarope/*filters.py` / `envtests.py` / `envglobals.py`, declaration + example in `src/jinjarope/resources/*.toml` |
| Environment behaviour | `src/jinjarope/environment.py` |
| Loaders | `src/jinjarope/loaders.py`, `fsspecloaders.py`, `configloaders.py`, `loaderregistry.py` |
| Docs site structure | `src/jinjarope/manual.py`, `docs/*.jinja`, `docs/*.md`, `mkdocs.yml` |
| CI | `.github/workflows/build.yml`, `.github/workflows/documentation.yml` |
| Tests / fixtures | `tests/`, `tests/testresources/` |

## Commands

```bash
uv sync --all-extras              # setup (default groups: dev, lint, docs)
uv run pytest                     # tests
uv run ruff check . && uv run ruff format --check .
uv run ty check                   # must exit 0; warnings fail too
uv run deptry src                 # dependency hygiene
uv run mknodes build       # docs (or: uv run duty build / duty serve)
uv build
```

`duties.py` also provides `lint`, `lint_check`, `test`, `update`, `version` (bumps and tags:
don't run it unless asked).

## Conventions

- Python >= 3.13, `from __future__ import annotations`, Google-style docstrings, line
  length 100, ruff preview formatting. ruff and ty are pinned in the `lint` group.
- Use targeted `# ty: ignore[rule]` only for real checker limitations (jinja2/fsspec stubs).
- Every TOML item should have at least one example: the docs build renders every example
  (`docs/filters.jinja`), so a broken example breaks the docs build.
- Tests are plain pytest functions in `tests/test_*.py`; `asyncio_mode = "auto"`.

## Pitfalls

- Managed with the copier-phil65 template (`.copier-answers.yml`): CI, hooks, ruff / ty config
  come from the template (`copier update`); project additions go below the "Only add below"
  markers in `pyproject.toml`.
- Optional deps (extras `cli`, `extras`, `httpx`/`httpx2`, `icons`, `llm`, `yaml`) must only be
  imported lazily or through TOML `fn` paths; `import jinjarope` must work with the core deps.
- Examples that need a model or network (e.g. `llm_complete` in `llm_filters.toml`) set
  `render = false`, so the docs show the template without executing it.
- `if __name__ == "__main__":` blocks must not import the module itself (breaks the docs build).
- Jinja parses `a | b` as a filter, so Python union syntax can't be used in examples.
- Objects defined in private modules (e.g. `pathlib.Path.cwd` -> `pathlib._abc`) are documented
  by their public dotted path (see `docs/filters.jinja`).
- `uv.lock` is gitignored.
