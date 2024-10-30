# LZV.nrw DCM Bag Builder
This package extends the `make_bag` method of the [`bagit` library](https://github.com/LibraryOfCongress/bagit-python) according to the specifications of the project [LZV.nrw](https://www.lzv.nrw/).

## Specifics
An instance of the DCM `BagBuilder` can be generated, with the optional arguments `manifests` and  `tagmanifests` to set the algorithms to be used when creating bags. The default checksums are imported from the default set in the [`bagit` library](https://github.com/LibraryOfCongress/bagit-python/blob/ed81c2384955747e8ba9dcb9661df1ac1fd31222/bagit.py#L131).
After instantiation, a `BagBuilder`-object provides the `make_bag`-method to create a BagIt-Bag and the property `log` (a `dcm-common` `Logger`-object) containing information on initialization and all build-jobs.

The deviation from the bags generated from the [`make_bag`](https://github.com/LibraryOfCongress/bagit-python/blob/ed81c2384955747e8ba9dcb9661df1ac1fd31222/bagit.py#L144)-method in the bagit-library consists of the following steps:
1. update the BagIt-Version in the `bagit.txt` to `1.0`,
2. update the bag info in the `bag-info.txt` to account for basic specifications of the LZV.nrw project:
    * addition of the field `Bagging-DateTime`, and
    * removal of the - now redundant - field `Bagging-Date`.
3. Optional: If a metadata directory is passed to the method, the directory is moved into the bag - but not into the payload - and the tagmanifest files are renewed.
4. If different algorithms for manifests and tag-manifests are requested, the bag is first created with the union of those two sets but afterwards 'cleaned up' (i.e. unwanted files and entries in tag-manifests are removed).

   This is due to the `bagit` library not supporting settings the two sets of algorithms individually.
5. Call the basic validation routine [`is_valid()`](https://github.com/LibraryOfCongress/bagit-python/blob/ed81c2384955747e8ba9dcb9661df1ac1fd31222/bagit.py#L613) from the `bagit` library to validate the bag before returning it.

## Setup
Install this package and its dependencies by issuing `pip install .` .

## Test
This repository contains test data for building a bag (located in `test_dcm_bag_builder/fixtures`):

Run `pytest`-Tests (install by `pip install pytest`) with `pytest -v -s --cov`.

# Contributors
* Sven Haubold
* Orestis Kazasidis
* Stephan Lenartz
* Kayhan Ogan
* Michael Rahier
* Steffen Richters-Finger
* Malte Windrath
