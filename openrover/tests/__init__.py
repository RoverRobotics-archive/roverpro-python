import pytest
from pytest_trio import enable_trio_mode

# if installing from an egg, the pytest.ini function may not exist
assert enable_trio_mode is not None


def main():
    return pytest.main(['--pyargs', 'openrover'])


if __name__ == '__main__':
    exit(main())
