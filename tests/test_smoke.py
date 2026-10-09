import jev


def test_package_exposes_version() -> None:
    assert jev.__version__ == "0.1.0"
