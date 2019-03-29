import importlib.util
import sys

import pytest


def main():
    return pytest.main(importlib.util.find_spec('openrover').submodule_search_locations + sys.argv[1:])


if __name__ == '__main__':
    exit(main())
