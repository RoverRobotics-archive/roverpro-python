from importlib.util import find_spec

import pytest


def main():
    openrover_search_paths = find_spec('openrover').submodule_search_locations
    return pytest.main(openrover_search_paths)


if __name__ == '__main__':
    exit(main())
