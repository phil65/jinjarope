# jinjarope

<div align="center">
  <picture>
    <img alt="JinjaRope"
         src="https://raw.githubusercontent.com/phil65/jinjarope/main/docs/logo.jpg"
         width="50%">
  </picture>
</div>

[![PyPI License](https://img.shields.io/pypi/l/jinjarope.svg)](https://pypi.org/project/jinjarope/)
[![Package status](https://img.shields.io/pypi/status/jinjarope.svg)](https://pypi.org/project/jinjarope/)
[![Daily downloads](https://img.shields.io/pypi/dd/jinjarope.svg)](https://pypi.org/project/jinjarope/)
[![Weekly downloads](https://img.shields.io/pypi/dw/jinjarope.svg)](https://pypi.org/project/jinjarope/)
[![Monthly downloads](https://img.shields.io/pypi/dm/jinjarope.svg)](https://pypi.org/project/jinjarope/)
[![Distribution format](https://img.shields.io/pypi/format/jinjarope.svg)](https://pypi.org/project/jinjarope/)
[![Wheel availability](https://img.shields.io/pypi/wheel/jinjarope.svg)](https://pypi.org/project/jinjarope/)
[![Python version](https://img.shields.io/pypi/pyversions/jinjarope.svg)](https://pypi.org/project/jinjarope/)
[![Implementation](https://img.shields.io/pypi/implementation/jinjarope.svg)](https://pypi.org/project/jinjarope/)
[![Releases](https://img.shields.io/github/downloads/phil65/jinjarope/total.svg)](https://github.com/phil65/jinjarope/releases)
[![Github Contributors](https://img.shields.io/github/contributors/phil65/jinjarope)](https://github.com/phil65/jinjarope/graphs/contributors)
[![Github Forks](https://img.shields.io/github/forks/phil65/jinjarope)](https://github.com/phil65/jinjarope/forks)
[![Github Issues](https://img.shields.io/github/issues/phil65/jinjarope)](https://github.com/phil65/jinjarope/issues)
[![Github Issues](https://img.shields.io/github/issues-pr/phil65/jinjarope)](https://github.com/phil65/jinjarope/pulls)
[![Github Watchers](https://img.shields.io/github/watchers/phil65/jinjarope)](https://github.com/phil65/jinjarope/watchers)
[![Github Stars](https://img.shields.io/github/stars/phil65/jinjarope)](https://github.com/phil65/jinjarope/stars)
[![Github Repository size](https://img.shields.io/github/repo-size/phil65/jinjarope)](https://github.com/phil65/jinjarope)
[![Github last commit](https://img.shields.io/github/last-commit/phil65/jinjarope)](https://github.com/phil65/jinjarope/commits)
[![Github release date](https://img.shields.io/github/release-date/phil65/jinjarope)](https://github.com/phil65/jinjarope/releases)
[![Github language count](https://img.shields.io/github/languages/count/phil65/jinjarope)](https://github.com/phil65/jinjarope)
[![Github commits this week](https://img.shields.io/github/commit-activity/w/phil65/jinjarope)](https://github.com/phil65/jinjarope)
[![Github commits this month](https://img.shields.io/github/commit-activity/m/phil65/jinjarope)](https://github.com/phil65/jinjarope)
[![Github commits this year](https://img.shields.io/github/commit-activity/y/phil65/jinjarope)](https://github.com/phil65/jinjarope)
[![Package status](https://codecov.io/gh/phil65/jinjarope/branch/main/graph/badge.svg)](https://codecov.io/gh/phil65/jinjarope/)

[Read the documentation!](https://phil65.github.io/jinjarope/)

**jinjarope** is a toolkit for [Jinja2](https://jinja.palletsprojects.com/): an enhanced
`Environment` with a large set of extra filters, tests and globals, loaders for
[fsspec](https://filesystem-spec.readthedocs.io/) filesystems and nested dicts, composable
loader classes, and TOML-based "JinjaFiles" to declare filters / tests / environment config.

## Installation

```bash
pip install jinjarope
```

Optional extras: `cli` (command line interface), `extras` (formatting, highlighting, humanize,
natsort filters), `httpx`, `icons` (icon filters), `llm` (`llm_complete` filter via agentpool),
`yaml`.

```bash
pip install "jinjarope[cli]"
```

## Quickstart

```python
import jinjarope

env = jinjarope.Environment(loader=jinjarope.DictLoader({"hello.jinja": "Hello {{ name }}!"}))
print(env.render_template("hello.jinja", name="World"))  # Hello World!
print(env.render_string("{{ 'Hello World' | slugify }}"))  # hello_world
```

## Features

- `jinjarope.Environment`: drop-in `jinja2.Environment` subclass with ~150 additional
  filters / tests / functions, `render_string` / `render_file` / `render_template`,
  `with_globals()`, selectable undefined behavior (`"strict"`, `"lax"`, ...), and an
  entry-point (`jinjarope.environment`) to let other packages extend every environment.
- Subclasses of all jinja2 loaders with `__eq__`, `__hash__`, `__repr__` and `__getitem__`,
  plus fsspec-based and dict-based loaders.
- JinjaFiles: TOML files declaring filters, tests, functions and environment config.
- A read-only fsspec filesystem exposing a loader's templates (for debugging).
- A `jinjarope` CLI to render (remote) templates: `jinjarope -i template.jinja -j config.toml -o out.md` (with the `cli` extra).

### FsSpecFileSystemLoader

Works like a `FileSystemLoader`, but on any fsspec-supported (remote) location.
Using the `dir::` prefix, any folder can be set as root.

```python
import fsspec
import jinjarope

# protocol path
loader = jinjarope.FsSpecFileSystemLoader("dir::github://phil65:jinjarope@main/tests/testresources")
env = jinjarope.Environment(loader=loader)
env.get_template("testfile.jinja").render()

# protocol and storage options
loader = jinjarope.FsSpecFileSystemLoader("github", org="phil65", repo="jinjarope")
env = jinjarope.Environment(loader=loader)
env.get_template("README.md").render()

# fsspec filesystem
fs = fsspec.filesystem("github", org="phil65", repo="jinjarope")
loader = jinjarope.FsSpecFileSystemLoader(fs)
env = jinjarope.Environment(loader=loader)
env.get_template("README.md").render()
```

### FsSpecProtocolPathLoader

Accepts complete fsspec protocol paths as template names.

```python
loader = jinjarope.FsSpecProtocolPathLoader()
env = jinjarope.Environment(loader=loader)
env.get_template("github://phil65:jinjarope@main/tests/testresources/testfile.jinja").render()
```

### NestedDictLoader

```toml
[example]
template = "{{ something }}"
```

```python
import tomllib

with open("templates.toml", "rb") as toml_file:
    content = tomllib.load(toml_file)
loader = jinjarope.NestedDictLoader(content)
env = jinjarope.Environment(loader=loader)
env.get_template("example/template").render(something="value")
```

### Loader composition

```python
loader = jinjarope.FileSystemLoader("templates/")
template = loader["path/to/template.jinja"]  # jinja2.Template
source = loader.get_template_source("path/to/template.jinja")

# OR loaders to get a ChoiceLoader
choice_loader = jinjarope.FileSystemLoader("templates/") | jinjarope.PackageLoader("my_package")

# pathlib-style division creates a PrefixLoader
prefix_loader = "path_prefix" / jinjarope.FileSystemLoader("templates/")
```

### Filters, tests and functions

See the [documentation](https://phil65.github.io/jinjarope/) for the full list of built-in
filters, tests and functions with examples.
