import pytest, openrover


def main():
    return pytest.main(openrover.__path__)

if __name__ == '__main__':
    exit(main())