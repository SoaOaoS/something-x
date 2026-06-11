from importlib.metadata import version as _pkg_version, PackageNotFoundError as _PNF


def _resolve_version() -> str:
    for pkg in ("something-x", "something-x-dev"):
        try:
            return _pkg_version(pkg)
        except _PNF:
            pass
    # Running from source: setuptools-scm writes _version.py at build/install time
    try:
        from ._version import __version__

        return __version__
    except ImportError:
        return "0.0.0+dev"


__version__ = _resolve_version()
APP_ID = "com.something.x.omarchy"
