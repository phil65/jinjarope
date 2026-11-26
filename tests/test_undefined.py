import pytest

import jinjarope


def test_lax_undefined():
    env = jinjarope.Environment(undefined="lax")
    env.render_string(r"{{ a.not_existing }}")


if __name__ == "__main__":
    pytest.main([__file__])
