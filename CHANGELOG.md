# Changelog

## [2.0.0] - 2024-09-05

### Changed

- **Breaking:** migrated to dcm-common (version 3) (`d7bd987e`)

## [1.0.0] - 2024-04-04

### Changed

- **Breaking:** changed build-method name to `build_bag` (`4402a772`)
- **Breaking:** changed build-method argument signature to take `exist_ok` to allow replacing existing target directories (`af35164e`, `ee23cb94`)
- **Breaking:** switched to new implementation of `lzvnrw_supplements.Logger` and renamed `report`-property to `log` (`083bb225`, `d8274b9b`)

### Added

- added py.typed marker to package (`39c68cf2`)

### Fixed

- replaced test-data by fake information (`6f9531cb`)

## [0.4.0] - 2023-11-23

### Added
- add `_get_bag_creation_time`-method to `BagBuilder`-class (`b97cdc7a`)

### Fixed
- unpin lzvnrw-dependencies (`e95280c5`)
- fixed conditional build/push pipeline (`c056e0c6`)

## [0.3.0] - 2023-10-20

### Changed

- initial release of the builder library
- update lzvnrw-supplements dependency-version (`619c4896`, `c03d2db7`)
