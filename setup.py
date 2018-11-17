import setuptools
import subprocess
import re


def get_git_version():
    version = subprocess.check_output(['git', 'describe', '--tags']).decode().strip()
    # check that version number is formatted correctly as ###.###.###
    assert re.fullmatch(r'\d+\.\d+\.\d+', version)
    return version


with open('README.md', 'r') as fh:
    long_description = fh.read()

    setuptools.setup(
        name="openrover",
        version=get_git_version(),
        author="Daniel Rose",
        author_email="dan@digilabs.io",
        description="A Python driver for driving the Rover Robotics OpenRover Basic robot",
        long_description=long_description,
        long_description_content_type="text/markdown",
        url="https://github.com/RoverRobotics/openrover_python_driver",
        packages=setuptools.find_packages(),
        python_requires='>=3.7',
        install_requires=[
            'pyserial',
        ],
        test_requires=[
            'pytest',
        ],
        classifiers=[
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.7",
            "License :: OSI Approved :: BSD License",
            "Operating System :: OS Independent",
        ],
    )
