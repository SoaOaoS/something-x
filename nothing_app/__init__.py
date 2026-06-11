from importlib.metadata import version as _pkg_version, PackageNotFoundError as _PNF


def _resolve_version() -> str:
    for pkg in ("something-x", "something-x-dev"):
        try:
            return _pkg_version(pkg)
        except _PNF:
            pass
    try:
        import tomllib
        import pathlib

        data = tomllib.loads((pathlib.Path(__file__).parent.parent / "pyproject.toml").read_text())
        return data["project"]["version"] + "+src"
    except Exception:
        return "0.0.0+dev"


__version__ = _resolve_version()
APP_ID = "com.something.x.omarchy"
