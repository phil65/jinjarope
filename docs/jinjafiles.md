**JinjaRope** supports a TOML file format to define the environment. This includes all filters, functions and tests as well as the environment configuration (strip_blocks etc.) and loaders.

A [jinjarope.JinjaFile][] looks like this:

```toml
[filters.name_of_filter]
fn = "mylibrary.some_filter"
group = "text"

[tests.name_of_test]
fn = "mylibrary.some_test"
group = "text"

[functions.name_of_function]
fn = "mylibrary.some_function"
group = "text"

[[loaders]]
type = "fsspec"
fs = "github://"

[config]
trim_blocks = true
...
```

These TOML files can be used to define an environment in a declarative way and can be combined as needed.

**JinjaRope** itself contains separate definition files for the **jinja2**-builtin filters / tests
and the **JinjaRope** filters / tests. The **jinja2**-definition files are only used for documentation (that way the documentation contains all filters / tests, so no need to juggle between different docs), the **JinjaRope** definition files will also get loaded by the jinjarope environment.

[JinjaFiles][jinjarope.JinjaFile] can get added to Environments easily via [jinjarope.Environment.load_jinja_file][jinjarope.envbase.EnvironmentBase.load_jinja_file].


In the following part the different sections of the TOML file will get explained.

### Defining filters

```toml
 # define a filter with a unique name

[filters.name_of_filter]
fn = "mylibrary.some_function"  # dotted path to the callable.
group = "text"  # used for the documentation
icon = "mdi:text"  # optional icon for the documentation
description = "..."  # additional description
aliases = ["e"]  # for adding shortcuts / aliases
required_packages = ["my_package"]  # will only add filter / test when given package is installed

# define an example for the docs
[filters.name_of_filter.examples.some_identifier]
title = "Example title"
description = "Some explanation text"
template = """
{ { some jinja example } }
"""
# markdown = true  # show the rendered result as a code block
# render = false  # only show the template, don't render it (e.g. needs network / an LLM)
...
```


### Defining tests

```toml
[tests.name_of_test]
... #  same fields as for filters
```

### Defining functions

```toml
[functions.name_of_function]
... #  same fields as for filters
```

### Defining loaders

Every loader defined in TOML requires a `type` (the loader's `ID`: "filesystem", "package", "module", "dict", "nested_dict", "template_file", "fsspec", "fsspec_protocol_path", "rewrite", "prefix" or "choice"), which is mapped to the corresponding loader class. Every further keyword - value pair is passed to the constructor of that loader (`prefix` additionally wraps the loader in a PrefixLoader).

```toml
[[loaders]]
type = "filesystem"
searchpath = "path/to/template/folder"

# we can define multiple loaders, this will result in a combined ChoiceLoader.

[[loaders]]
type = "fsspec"
fs = "github://phil65:jinjarope@main"

[[loaders]]
type = "package"
package = "jinjarope"
```
*Pay attention to the double brackets, that´s how lists are defined in TOML!*

### Defining the environment config

These are all available options for the environment.
Refer to the jinja2 docs for more information.

```toml
[config]
trim_blocks = ...
block_start_string = ...
block_end_string = ...
variable_start_string = ...
variable_end_string = ...
comment_start_string = ...
comment_end_string = ...
line_statement_prefix = ...
line_comment_prefix = ...
trim_blocks = ...
lstrip_blocks = ...
newline_sequence = ...
keep_trailing_newline = ...
...
```
