from __future__ import annotations

import mknodes as mk
from mknodes.manual import dev_section

from jinjarope import JinjaItem, inspectfilters, iterfilters, jinjafile, mdfilters


RESOURCE_PATH = "src/jinjarope/resources"
FILES = [
    "filters.toml",
    "functions.toml",
    "tests.toml",
    "jinja_filters.toml",
    "jinja_functions.toml",
    "jinja_tests.toml",
    "humanize_filters.toml",
    "llm_filters.toml",
]


def table_for_items(items: list[JinjaItem]) -> mk.MkTable:
    t = mk.MkTable(columns=["Name", "Description"])
    for item in items:
        link = mdfilters.autoref_link(item.identifier, item.identifier)
        doc = inspectfilters.get_doc(item.filter_fn, only_summary=True)
        t.add_row((link, doc))
    return t


class Build:
    @classmethod
    def build(cls, root: mk.MkNav, theme: mk.Theme) -> mk.MkNav:
        b = cls()
        # b.on_theme(theme)
        return b.on_root(root)

    def on_root(self, nav: mk.MkNav) -> mk.MkNav:
        self.nav = nav
        nav.page_template.announcement_bar = mk.MkMetadataBadges("websites")
        page = nav.add_page(is_index=True, hide="nav,toc")
        page += mk.MkText(page.ctx.metadata.description)
        self.add_sections()
        extending_nav = mk.MkNav("Extensions")
        nav += extending_nav
        page = extending_nav.add_page("Entry points", hide="toc")
        page += mk.MkTemplate("extensions.md")
        page = extending_nav.add_page("JinjaFiles", hide="toc")
        page += mk.MkTemplate("jinjafiles.md")
        nav.add_doc(section_name="API", flatten_nav=True, recursive=True)
        page = nav.add_page("CLI", hide="nav")
        page += mk.MkTemplate("cli.jinja")
        nav += dev_section.nav
        return nav

    def add_sections(self) -> None:
        sections: dict[str, list[jinjafile.JinjaItem]] = {
            "Filters": [],
            "Tests": [],
            "Functions": [],
        }
        for path in FILES:
            file = jinjafile.JinjaFile(f"{RESOURCE_PATH}/{path}")
            sections["Filters"].extend(file.filters)
            sections["Tests"].extend(file.tests)
            sections["Functions"].extend(file.functions)
        for title, items in sections.items():
            nav = self.nav.add_nav(title)
            filters_index = nav.add_page(title, is_index=True, hide="toc")
            grouped = iterfilters.groupby(items, key="group", natural_sort=True)
            for group, filters in grouped.items():
                p = mk.MkPage(f"{group} ({len(filters)})")
                nav += p
                variables = dict(mode=title.lower(), items=list(filters))
                p += mk.MkTemplate("filters.jinja", variables=variables)
                filters_index += f"## {group}"
                filters_index += table_for_items(filters)


if __name__ == "__main__":
    build = Build()
    nav = mk.MkNav("JinjaRope")
    theme = mk.MaterialTheme()
    build.build(nav, theme)
    print(nav)
