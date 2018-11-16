import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

    setuptools.setup(
        name="openrover",
        version="0.0.2",
        author="Daniel Rose",
        author_email="dan@digilabs.io",
        description="A Python driver for driving the Rover Robotics OpenRover Basic robot",
        long_description=long_description,
        long_description_content_type="text/markdown",
        url="https://github.com/RoverRobotics/openrover_python_driver",
        packages=setuptools.find_packages(),
        install_requires=[
            'pyserial',
            'pytest',
        ],
        classifiers=[
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.7",
            "License :: OSI Approved :: BSD License",
            "Operating System :: OS Independent",
        ],
    )
