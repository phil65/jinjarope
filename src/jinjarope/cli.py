from __future__ import annotations

import typer as t

import jinjarope


CFG_HELP = "JinjaFiles to load."
OUT_HELP = "Output path for resolved template. If not given, print to stdout."
IN_HELP = "Path to a (remote) template file."
UNDEF_HELP = "Set undefined behavior. Overrides JinjaFiles settings."
TRIM_HELP = "Trim blocks. Overrides JinjaFiles settings."

CFG_CMDS = ["-j", "--jinja-file"]
OUT_CMDS = ["-o", "--output-file"]
IN_CMDS = ["-i", "--input-file"]
UNDEF_CMDS = ["-u", "--undefined"]
TRIM_CMDS = ["-t", "--trim-blocks"]


cli = t.Typer(
    name="JinjaRope",
    help=(
        " 🚀🚀🚀 JinjaRope CLI interface. Render templates from the terminal! 🚀🚀🚀\n\n"
        "Check out https://phil65.github.io/jinjarope/ !"
    ),
    no_args_is_help=True,
)


@cli.command()
def render(
    template_path: str = t.Option(
        None,
        *IN_CMDS,
        help=IN_HELP,
        show_default=False,
    ),
    cfg_files: list[str] = t.Option(  # noqa: B008
        None,
        *CFG_CMDS,
        help=CFG_HELP,
        show_default=False,
    ),
    output: str = t.Option(
        None,
        *OUT_CMDS,
        help=OUT_HELP,
        show_default=False,
    ),
    undefined: str = t.Option(
        "strict",
        *UNDEF_CMDS,
        help=UNDEF_HELP,
        show_default=False,
    ),
    trim_blocks: bool = t.Option(
        None,
        *TRIM_CMDS,
        help=TRIM_HELP,
        show_default=False,
    ),
) -> None:
    """Render a Jinja template.

    Args:
        template_path: Path to a (remote) template file.
        cfg_files: JinjaFiles to load.
        output: Output path for resolved template. If not given, print to stdout.
        undefined: Set undefined behavior. Overrides JinjaFiles settings.
        trim_blocks: Trim blocks. Overrides JinjaFiles settings.
    """
    env = jinjarope.Environment()
    for path in cfg_files:
        env.load_jinja_file(path)
    if undefined:
        env.set_undefined(undefined)  # type: ignore[arg-type]
    if trim_blocks is not None:
        env.trim_blocks = trim_blocks
    text = env.render_file(template_path)
    if output is None:
        print(text)
    else:
        import fsspec  # type: ignore[import-untyped]

        with fsspec.open(output, mode="w", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    cli(
        [
            "-i",
            "github://phil65:mknodes@main/docs/icons.jinja",
            "-j",
            "src/jinjarope/resources/tests.toml",
            "-j",
            "src/jinjarope/resources/filters.toml",
            "-o",
            "out.test",
        ],
    )
