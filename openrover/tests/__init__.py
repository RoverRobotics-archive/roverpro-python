import pytest


def main():
    return pytest.main(['--pyargs', 'openrover'])


if __name__ == '__main__':
    exit(main())
