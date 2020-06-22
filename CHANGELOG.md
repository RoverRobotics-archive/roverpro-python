# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- New tests for overspeed fault behavior
- New tests for fan speed behavior
- Testing with Tox to ensure compatibility with all supported Python versions
- New Verbs:
  232 = CLEAR_SYSTEM_FAULT
  16 = SET_OVERSPEED_ENCODER_THRESHOLD_ENCODER_100HZ
  17 = SET_OVERSPEED_DURATION_100MS
  18 = SET_BRAKE_ON_FAULT
- New Data Elements:
  78 = fan1 duty
  80 = fan2 duty
  82 = system fault flags (overspeed / overcurrent)

### Fixed
- Serial error handling could previously throw a TypeError on failure to connect to a device instead of an OpenRoverException
- No more warning when running on Ubuntu: "RuntimeWarning: You seem to already have a custom sys.excepthook handler installed."

### Changed
- More docs.
- Dropped support for Python3.5
- (dev) This project now builds with `poetry` instead of `setuptools` to provide simpler release process.
- (dev) Code formatting is now done with Black.

## [0.3.1] - 2019-05-08
------------------
### Added
- Add new configuration options for speed in hHz and speed limit
  percent. [Dan Rose]

### Fixed
- Fix improper reporting of version number for legacy firmware.

0.2.1 (2019-04-22)
------------------
### Added
- Python 3.5 compatibility.
- Add new settings command verbs. [Dan Rose]
- Add pitstop, a command line utility to bootload and configure the
  rover.
- Add license, package for pypi
- Many new tests

### Changed
- Changed license from BSD 2-clause to 3-clause
- Update TIME_TO_FULL_SPEED to make it in deciseconds.
- Use Trio for async

### Fixed
- Fix requirement for setuptools_scm (should be setuptools-scm)
- Fixed issue which made protocol test fail

0.0 (2018-11-14)
----------------
### Added
- Basic Python Driver functionality

[Unreleased]: https://github.com/olivierlacan/keep-a-changelog/compare/0.3.1...HEAD
[0.3.1]: https://github.com/RoverRobotics/openrover-python/compare/0.2.1...0.3.1
[0.2.1]: https://github.com/RoverRobotics/openrover-python/compare/0.0...0.2.1
[0.2a3]: https://github.com/RoverRobotics/openrover-python/compare/0.1.0...v0.2.0
[0.2a2]: https://github.com/RoverRobotics/openrover-python/compare/0.1a7...0.2a2
[0.1a7]: https://github.com/RoverRobotics/openrover-python/compare/0.1a5...0.1a7
[0.1a5]: https://github.com/RoverRobotics/openrover-python/compare/0.0...0.1a5