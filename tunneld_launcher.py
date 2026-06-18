import importlib.metadata as metadata


_metadata_version = metadata.version


def _safe_version(name: str) -> str:
    try:
        return _metadata_version(name)
    except metadata.PackageNotFoundError:
        if name == "pymobiledevice3":
            return "0"
        raise


metadata.version = _safe_version

from pymobiledevice3.__main__ import main

if __name__ == '__main__':
    main()
