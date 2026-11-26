import pytest

import jinjarope


def test_rewrite_loader():
    loader = jinjarope.FileSystemLoader("")
    rewrite_loader = jinjarope.RewriteLoader(loader, lambda p, x: x.replace("C", "XXX"))
    env = jinjarope.Environment()
    env.loader = rewrite_loader
    result = env.render_template("tests/testresources/testfile.jinja")
    assert result.startswith("XXX")


if __name__ == "__main__":
    pytest.main([__file__])
