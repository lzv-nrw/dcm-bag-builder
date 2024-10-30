"""
This module contains pytest-tests for testing the features of the builder.

All tests use the test data and meta located in test_dcm_bag_builder/fixtures/test_data.
The test data/meta are copied to a TESTING_DIR during the test initialization.
TESTING_DIR can be safely removed after the tests.
"""

from shutil import copytree, rmtree
from pathlib import Path
from itertools import combinations, product
from re import fullmatch as re_fullmatch

import pytest
import hypothesis.strategies as st
from hypothesis import given, settings
import bagit
from dcm_common import util, LoggingContext as Context

from dcm_bag_builder import builder

FIXTURES_DIR = Path("test_dcm_bag_builder/fixtures")
BAGIT_PROFILE_TEST = FIXTURES_DIR / "test_profile.json"
TESTING_DIR = FIXTURES_DIR / "tmp"
TEST_IE_SUBDIR = "test_ie"
BAG_DIR = TESTING_DIR / "test_bag"
META_DIR = TESTING_DIR / "test_meta"
EXAMPLE_BAG_INFO = {
    "Bag-Software-Agent": "dcm-cli v0.0.0",
    "Source-Organization": "https://d-nb.info/gnd/000000000",
    "External-Identifier": "3192@9361250 c-dd0d-4a76-a2c7-c18de46502a6",
    "Origin-System-Identifier": "Quellsystem-Identifier",
    "DC-Creator": "Max Muster, et al.",
    "DC-Title": "Some title",
    "DC-Terms-Identifier": "doi: 10.0000/abc/0-000",
    "DC-Rights": "Public Domain",
    "DC-Terms-Rights": "https://rightsstatements.org/vocab/InC/1.0/",
    "DC-Terms-License": "https://creativecommons.org/licenses/by/4.0/",
    "DC-Terms-Access-Rights": "https://purl.org/coar/access_right/c_abf2",
    "Embargo-Enddate": "2024-01-01",
    "DC-Terms-Rights-Holder": "https://orcid.org/0000-0000-0000-0000",
    "Preservation-Level": "Logical"
}
DEFAULT_CHECKSUMS = builder.DEFAULT_CHECKSUMS.copy()


@pytest.fixture(scope="session", autouse=True)
def cleanup(request):
    """
    Clean up tmp dir
    """

    request.addfinalizer(
        lambda: rmtree(TESTING_DIR) if TESTING_DIR.is_dir() else None
    )


def copy_directory(
        source_path: str | Path,
        dest_path: str | Path,
        force: bool = False,
        keep_source: bool = True
):
    copytree(src=source_path, dst=dest_path, dirs_exist_ok=force)
    if not keep_source:
        rmtree(source_path)


def load_baginfo(path):
    result = {}
    for line in Path(path).read_text(encoding="utf-8").split("\n"):
        if ":" not in line:
            continue
        field = tuple(map(lambda s: s.strip(), line.split(":", maxsplit=1)))
        if field[0] in result:
            result[field[0]] = [result[field[0]]]
        else:
            result[field[0]] = field[1]
    return result


def test_bag_creation_time():
    # Load a profile
    some_profile = util.get_profile(BAGIT_PROFILE_TEST)
    # Get regular expression for the field Bagging-DateTime
    datetime_specification = (some_profile["Bag-Info"]
                                          ["Bagging-DateTime"]
                                          ["description"])
    # Get the current time
    current_time = builder.BagBuilder()._get_bag_creation_time()
    # Assert that the current time matches the specification
    assert re_fullmatch(datetime_specification, current_time)


def initiate_test(example_path=FIXTURES_DIR / "test_data"):
    """
    Initiate the tests for _call_bagit.
    To be used in the arrange step of a test
    """

    # Reset the example data and metadata
    copy_directory(
        source_path=example_path / "data",
        dest_path=BAG_DIR / "data",
        keep_source=True
    )
    copy_directory(
        source_path=example_path / "meta",
        dest_path=BAG_DIR / "meta",
        keep_source=True
    )

    return EXAMPLE_BAG_INFO.copy()


def test_plain_specifications():
    """
    Test the _call_bagit method, with just the directory - the minimum requirement.
    Validate the bag version and
    further fields from the specifications of the LZV project.
    """

    # Test_Arrange
    # Initiate the test
    _ = initiate_test()

    # Test_Act
    # Create the bag
    Bag_LZV_instance = builder.BagBuilder()._call_bagit(src=BAG_DIR)

    # Read the bagit.txt"
    content_bagit = (BAG_DIR / "data" / "bagit.txt").read_text(encoding="utf-8")
    split_content_bagit = content_bagit.split("BagIt-Version: ")

    # Test_Assert
    # Validate the bag version
    assert split_content_bagit[1].startswith("1.0\n")
    assert Bag_LZV_instance.version_info == (1, 0)
    with pytest.deprecated_call():
        assert Bag_LZV_instance.version == "1.0"
        assert Bag_LZV_instance._version == "1.0"
    # A valid bag is generated
    assert Bag_LZV_instance is not None

    # Test_Cleanup
    # Delete the generated folders
    rmtree(BAG_DIR)


def test_default_checksums(test_checksums=DEFAULT_CHECKSUMS):
    """
    Test the _call_bagit method, with just the directory - the minimum requirement
    """

    # Test_Arrange
    # Initiate the test
    _ = initiate_test()

    # Test_Act
    # Create the bag
    Bag_LZV_instance = builder.BagBuilder()._call_bagit(src=BAG_DIR)
    # Get contents of bag root
    bag_content = [f.name for f in (BAG_DIR / "data").iterdir()]
    # Get existing manifest files
    existing_manifests = [
        mfile for mfile in bag_content if mfile.startswith("manifest-")
    ]
    existing_tag_manifests = [
        mfile for mfile in bag_content if mfile.startswith("tagmanifest-")
    ]
    # Create expected manifest files
    expected_manifests = [
        "".join(["manifest-", checksum, ".txt"])
        for checksum in test_checksums
    ]
    expected_tag_manifests = [
        "".join(["tagmanifest-", checksum, ".txt"])
        for checksum in test_checksums
    ]

    # Test_Assert
    # A valid bag is generated
    assert Bag_LZV_instance is not None
    # Assert that only the expected_manifests and expected_tag_manifests
    # for DEFAULT_CHECKSUMS were generated
    assert set(expected_manifests) == set(existing_manifests)
    assert set(expected_tag_manifests) == set(existing_tag_manifests)

    # Test_Cleanup
    # Delete the generated folders
    rmtree(BAG_DIR)


def test_with_list_value():
    """
    Test the _call_bagit method with all arguments
    and a list of values for a key with allowed cardinality > 1
    """

    # Test_Arrange
    # Initiate the test
    bag_info = initiate_test()

    # Test_Act
    # Manipulate the bag_info
    # Select the key to override
    # Possible for the fields: "DC-Creator", "DC-Title" and "DC-Terms-Identifier"
    # https://zivgitlab.uni-muenster.de/ULB/lzvnrw/team-konzeption/spec-information_package/-/blob/af8f7536b3f6694a9270317537dbe73d85b51f07/dcm_bagit_spezifikation.md
    # Override the field "DC-Creator" with a list of values.
    test_field = "DC-Creator"
    new_values = ["author1", "author2", 3]
    bag_info[test_field] = new_values

    # Create the bag
    Bag_LZV_instance = builder.BagBuilder()._call_bagit(
        src=BAG_DIR, bag_info=bag_info,
        processes=1, encoding="utf-8")
    # Read the bag-info.txt
    content_baginfo = (BAG_DIR / "data" / "bag-info.txt").read_text(encoding="utf-8")
    # Split the content in every occurrence of the test_field followed by ": "
    split_content = content_baginfo.split(test_field + ": ")

    # Test_Assert
    # A valid bag is generated
    assert Bag_LZV_instance is not None
    # The content of bag-info.txt is split into three parts
    # by the two occurrences of test_field
    assert len(split_content) == len(new_values) + 1
    # The (i+1)-th part of split content starts with the i-th value
    for i, new_value in enumerate(new_values):
        assert split_content[i+1].startswith(str(new_value))

    # Test_Cleanup
    # Delete the generated folder
    rmtree(BAG_DIR)


# hypothesis.errors.DeadlineExceeded: Test took 574.33ms, which exceeds the deadline of 200.00ms
@settings(deadline=None, max_examples=20)
# Generate a list (min_size=2, max_size=20) of strings (min_size=1)
# Exclude the characters from blacklist_categories
# https://en.wikipedia.org/wiki/Unicode_character_property#General_Category
# Remove leading and trailing whitespaces
@given(new_values=st.lists(st.text(
    min_size=1,
    alphabet=st.characters(
        blacklist_categories=("Cc", "Cs", "Cn", "Co", "Zl", "Zp", "So",)
    )
).map(lambda x: x.lstrip().rstrip()), min_size=2, max_size=20))
def test_hypothesis_with_list_value(new_values):
    """
    Test the _call_bagit method with all arguments
    and a random list of values created by the Hypothesis library
    for a key with allowed cardinality > 1
    """

    # Test_Arrange
    # Initiate the test
    bag_info = initiate_test()

    # Test_Act
    # Manipulate the bag_info
    # Select the key to override
    # Possible for the fields: "DC-Creator", "DC-Title" and "DC-Terms-Identifier"
    # https://zivgitlab.uni-muenster.de/ULB/lzvnrw/team-konzeption/spec-information_package/-/blob/af8f7536b3f6694a9270317537dbe73d85b51f07/dcm_bagit_spezifikation.md
    # Override the field "DC-Creator" with a list of values.
    test_field = "DC-Creator"
    bag_info[test_field] = new_values

    # Create the bag
    Bag_LZV_instance = builder.BagBuilder()._call_bagit(
        src=BAG_DIR, bag_info=bag_info,
        processes=1, encoding="utf-8")
    # Read the bag-info.txt
    content_baginfo = (BAG_DIR / "data" / "bag-info.txt").read_text(encoding="utf-8")
    # Split the content in every occurrence of the test_field followed by ": "
    split_content = content_baginfo.split(test_field + ": ")

    # Test_Assert
    # A valid bag is generated
    assert Bag_LZV_instance is not None
    # The content of bag-info.txt is split into three parts
    # by the two occurrences of test_field
    assert len(split_content) == len(new_values) + 1
    # The (i+1)-th part of split content starts with the i-th value
    for i, new_value in enumerate(new_values):
        assert split_content[i+1].startswith(new_value)

    # Test_Cleanup
    # Delete the generated folder
    rmtree(BAG_DIR)


def test_make_bag_from_IE_inplace(
    example_dir=FIXTURES_DIR / TEST_IE_SUBDIR
):
    """ Test making a bag from an IE with inplace True """

    # Copy IE_dir to keep the test data
    IE_dir = TESTING_DIR / TEST_IE_SUBDIR
    copy_directory(
        source_path=example_dir,
        dest_path=IE_dir,
        keep_source=True
    )

    # Create the bag
    test_builder = builder.BagBuilder()
    Bag_IE = test_builder.make_bag(
        src=IE_dir,
        bag_info=EXAMPLE_BAG_INFO.copy(),
        exist_ok=True
    )

    # Test_Assert
    # A bag is generated
    assert Bag_IE is not None
    # The origin folder is maintained
    assert example_dir.is_dir()
    # The folders inside the bag have the expected names
    folders = [x.name for x in IE_dir.glob("*") if x.is_dir()]
    assert sorted(folders) == sorted(["data", "meta"])
    # The files inside the bag have the expected names
    files = [x.name for x in IE_dir.glob("*") if x.is_file()]
    files.remove("bagit.txt")
    files.remove("bag-info.txt")
    assert files == [x for x in files if x.startswith(
        ("manifest", "tagmanifest"))
    ]
    # Assert the EXAMPLE_BAG_INFO is contained in bag-info.txt
    bag_info_dict = load_baginfo(IE_dir / "bag-info.txt")
    assert bag_info_dict.items() >= EXAMPLE_BAG_INFO.items()

    # Test_Cleanup
    # Delete the folder
    rmtree(IE_dir)


def test_make_bag_from_IE_inplace_False(
    example_dir=FIXTURES_DIR / TEST_IE_SUBDIR
):
    """ Test making a bag from an IE with inplace False """

    # Copy IE_dir to keep the test data
    IE_dir = TESTING_DIR / TEST_IE_SUBDIR
    copy_directory(
        source_path=example_dir,
        dest_path=IE_dir,
        keep_source=True
    )

    # Create the bag
    bag_path = str(IE_dir.parent) + "/" + IE_dir.name + "_bag"
    Bag_IE = builder.BagBuilder().make_bag(
        src=IE_dir,
        dest=bag_path,
        bag_info=EXAMPLE_BAG_INFO.copy()
    )
    # Open the bag from its directory (it's not the IE_dir)
    if isinstance(bag_path, str):
        bag_path = Path(bag_path)
    Bag_IE = bagit.Bag(str(bag_path))

    # Test_Assert
    # A bag is generated
    assert Bag_IE is not None
    # The origin folder is maintained
    assert example_dir.is_dir()
    # Both folders exist, because the Bag was created with inplace False.
    assert IE_dir.is_dir()
    assert bag_path.is_dir()
    # The folders inside the bag have the expected names
    folders = [x.name for x in bag_path.glob("*") if x.is_dir()]
    assert sorted(folders) == sorted(["data", "meta"])
    # The files inside the bag have the expected names
    files = [x.name for x in bag_path.glob("*") if x.is_file()]
    files.remove("bagit.txt")
    files.remove("bag-info.txt")
    assert files == [x for x in files if x.startswith(
        ("manifest", "tagmanifest"))
    ]

    # Test_Cleanup
    # Delete the folders
    rmtree(IE_dir)
    rmtree(bag_path)


def test_make_bag_existing_output_path(
    example_dir=FIXTURES_DIR / TEST_IE_SUBDIR,
    output_path=TESTING_DIR / "test_existing_folder"
):
    """
    Test making a bag when the output_path already exists
    """

    # Copy IE_dir to keep the test data
    IE_dir = TESTING_DIR / TEST_IE_SUBDIR
    copy_directory(
        source_path=example_dir,
        dest_path=IE_dir,
        keep_source=True
    )

    # Create a folder named output_path in the root directory
    output_path.mkdir(exist_ok=False)

    # Attempt to make a bag and catch exception
    with pytest.raises(FileExistsError) as exc_info:
        builder.BagBuilder().make_bag(
            src=IE_dir,
            dest=output_path,
            bag_info=EXAMPLE_BAG_INFO.copy()
        )

    # Test_Assert
    assert exc_info.type is FileExistsError
    assert str(output_path) in str(exc_info.value)

    # Test_Cleanup
    # Delete the folders
    rmtree(IE_dir)
    rmtree(output_path)


def test_make_bag_existing_folder_named_data(
    example_dir=FIXTURES_DIR / TEST_IE_SUBDIR
):
    """
    Test making a bag when a non-empty folder named 'data'
    already exists in the root directory
    """

    # Copy IE_dir to keep the test data
    IE_dir = TESTING_DIR / TEST_IE_SUBDIR
    copy_directory(
        source_path=example_dir,
        dest_path=IE_dir,
        keep_source=True
    )

    # Create a folder named 'data' in the root directory
    data_folder = IE_dir.parent / "data"
    data_folder.mkdir(exist_ok=False)
    # Create a file in the folder
    util.write_test_file(data_folder / "a_txt_file.txt")

    # Create the bag
    Bag_IE = builder.BagBuilder().make_bag(
        src=IE_dir, bag_info=EXAMPLE_BAG_INFO.copy()
    )

    # Test_Assert
    # A bag is generated
    assert Bag_IE is not None
    # The origin folder is maintained
    assert example_dir.is_dir()
    # Both folders exist, because the Bag was created with inplace False.
    assert IE_dir.is_dir()

    # Test_Cleanup
    # Delete the folders
    rmtree(IE_dir)
    rmtree(data_folder)


def test_make_bag_of_bag(
    example_dir=FIXTURES_DIR / TEST_IE_SUBDIR
):
    """
    Test making a bag from a folder containing a bag
    """

    # Copy IE_dir to keep the test data
    IE_dir = TESTING_DIR / TEST_IE_SUBDIR
    copy_directory(
        source_path=example_dir,
        dest_path=IE_dir,
        keep_source=True
    )

    # Initiate the BagBuilder
    test_builder = builder.BagBuilder()
    # Create the bag
    test_builder.make_bag(
        src=str(IE_dir),
        bag_info=EXAMPLE_BAG_INFO.copy()
    )

    # Attempt to create a bag from the bag
    bad_bag = test_builder.make_bag(
        src=IE_dir,
        bag_info=EXAMPLE_BAG_INFO.copy()
    )

    assert bad_bag is None
    # Test_Assert
    assert len(test_builder.log[Context.ERROR]) > 0

    # Test_Cleanup
    # Delete the folders
    rmtree(IE_dir)


def test_make_bag_no_bag_info_dict(
    example_dir=FIXTURES_DIR / TEST_IE_SUBDIR
):
    """
    Test making a bag without providing an bag-info dict.
    """

    # Copy IE_dir to keep the test data
    IE_dir = TESTING_DIR / TEST_IE_SUBDIR
    copy_directory(
        source_path=example_dir,
        dest_path=IE_dir,
        keep_source=True
    )

    # Delete the meta folder
    rmtree(IE_dir / "meta")

    # Initiate the BagBuilder
    test_builder = builder.BagBuilder()

    # Attempt to create the bag and catch exception
    with pytest.raises(TypeError) as exc_info:
        test_builder.make_bag(src=IE_dir)

    # Test_Assert
    assert exc_info.type is TypeError
    assert str(exc_info.value) ==\
        "BagBuilder.make_bag() missing 1 required positional argument: 'bag_info'"

    # Test_Cleanup
    # Delete the folders
    rmtree(IE_dir)


POSSIBLE_ALGORITHMS = DEFAULT_CHECKSUMS
# Create all possible combinations
COMBOS = []
for i in range(1, len(POSSIBLE_ALGORITHMS)+1):
    for j in range(1, len(POSSIBLE_ALGORITHMS)+1):
        COMBOS.extend(
            product(combinations(POSSIBLE_ALGORITHMS, i),
                    combinations(POSSIBLE_ALGORITHMS, j)
            )
        )
# Convert nested tuples to lists
COMBOS = [(list(item[0]), list(item[1])) for item in COMBOS]
@pytest.mark.parametrize("manifest_algorithms, tagmanifest_algorithms", COMBOS)
def test_make_bag_diff_algorithms_for_manifests(
    manifest_algorithms,
    tagmanifest_algorithms,
    example_dir=FIXTURES_DIR / TEST_IE_SUBDIR
):
    """
    Test making a bag with different algorithms
    for the manifest and tag-manifest files.
    """

    # Copy IE_dir to keep the test data
    IE_dir = TESTING_DIR / TEST_IE_SUBDIR
    copy_directory(
        source_path=example_dir,
        dest_path=IE_dir,
        keep_source=True
    )

    # Initiate the builder
    test_builder = builder.BagBuilder(manifest_algorithms, tagmanifest_algorithms)

    # Create the bag
    Bag_IE = test_builder.make_bag(
        src=IE_dir,
        bag_info=EXAMPLE_BAG_INFO.copy()
    )

    # Create expected manifest files
    expected_manifests = [
        "".join(["manifest-", checksum, ".txt"])
        for checksum in manifest_algorithms
    ]
    expected_tagmanifests = [
        "".join(["tagmanifest-", checksum, ".txt"])
        for checksum in tagmanifest_algorithms
    ]
    # Find existing manifest files
    existing_manifests = util.list_directory_content(
        IE_dir,
        pattern="*",
        condition_function=lambda p : p.name.startswith("manifest-")
    )
    existing_manifests = [p.name for p in existing_manifests]
    existing_tagmanifests = util.list_directory_content(
        IE_dir,
        pattern="*",
        condition_function=lambda p : p.name.startswith("tagmanifest-")
    )
    existing_tagmanifests = [p.name for p in existing_tagmanifests]

    # Test_Assert
    # A bag is generated
    assert Bag_IE is not None
    # The bag is valid
    assert Bag_IE.is_valid(fast=False, completeness_only=False)
    # Assert that only the expected_manifests and expected_tag_manifests
    # were generated
    assert set(expected_manifests) == set(existing_manifests)
    assert set(expected_tagmanifests) == set(existing_tagmanifests)

    # Test_Cleanup
    # Delete the folders
    rmtree(IE_dir)


def test_make_bag_no_meta_folder(
    example_dir=FIXTURES_DIR / TEST_IE_SUBDIR
):
    """
    Test making a bag from a directory without a 'meta' folder
    """

    # Copy IE_dir to keep the test data
    IE_dir = TESTING_DIR / TEST_IE_SUBDIR
    copy_directory(
        source_path=example_dir,
        dest_path=IE_dir,
        keep_source=True
    )

    # Delete the meta folder
    rmtree(IE_dir / "meta")

    # Initiate the BagBuilder
    test_builder = builder.BagBuilder()

    # Create the bag
    Bag_IE = test_builder.make_bag(
        src=IE_dir,
        bag_info=EXAMPLE_BAG_INFO.copy()
    )

    # Test_Assert
    # A bag is generated
    assert Bag_IE is not None
    # The bag is valid
    assert Bag_IE.is_valid(fast=False, completeness_only=False)

    # Test_Cleanup
    # Delete the folders
    rmtree(IE_dir)


def test_additional_baginfo_from_builder(
    example_dir=FIXTURES_DIR / TEST_IE_SUBDIR
):
    """
    Test the make_bag method
    to ensure it adds just two specific fields in bag-info.txt.
    """

    # Copy IE_dir to keep the test data
    IE_dir = TESTING_DIR / TEST_IE_SUBDIR
    copy_directory(
        source_path=example_dir,
        dest_path=IE_dir,
        keep_source=True
    )

    # Initiate the builder
    test_builder = builder.BagBuilder()

    # Load the bag-info
    bag_info_source = EXAMPLE_BAG_INFO.copy()

    # Create the bag
    Bag_IE = test_builder.make_bag(
        src=IE_dir, bag_info=bag_info_source.copy()
    )

    # Load the bag-info.txt
    bag_info_bag = load_baginfo(IE_dir / "bag-info.txt")

    # Test_Assert
    # A valid bag is generated
    assert Bag_IE is not None
    # Compare bag_info_bag with bag_info_source
    # Just two additional keys, namely 'Bagging-Date' and 'Payload-Oxum'
    assert set(bag_info_bag.keys()) - set(bag_info_source.keys()) ==\
        {'Payload-Oxum', 'Bagging-DateTime'}
    # All other entries are equal
    assert all(bag_info_bag[key] == value\
        for key, value in bag_info_source.items())

    # Test_Cleanup
    # Delete the generated folder
    rmtree(IE_dir)


def test_make_bag_no_data_folder(
    example_dir=FIXTURES_DIR / TEST_IE_SUBDIR
):
    """
    Test making a bag from a directory without a 'data' folder
    """

    # Copy IE_dir to keep the test data
    IE_dir = TESTING_DIR / TEST_IE_SUBDIR
    copy_directory(
        source_path=example_dir,
        dest_path=IE_dir,
        keep_source=True
    )

    # Delete the data folder
    rmtree(IE_dir / "data")

    # Initiate the BagBuilder
    test_builder = builder.BagBuilder()

    # Attempt to make a bag
    bad_bag = test_builder.make_bag(
        src=IE_dir,
        bag_info=EXAMPLE_BAG_INFO.copy()
    )

    # Test_Assert
    assert bad_bag is None
    assert len(test_builder.log[Context.ERROR]) > 0

    # Test_Cleanup
    # Delete the folders
    rmtree(IE_dir)


def test_make_bag_renamed_data_folder(
    example_dir=FIXTURES_DIR / TEST_IE_SUBDIR
):
    """
    Test making a bag from a directory after renaming the 'data' folder
    """

    # Copy IE_dir to keep the test data
    IE_dir = TESTING_DIR / TEST_IE_SUBDIR
    copy_directory(
        source_path=example_dir,
        dest_path=IE_dir,
        keep_source=True
    )

    # Rename the 'data' folder
    (IE_dir / "data").rename(IE_dir / "some_data")

    # Initiate the BagBuilder
    test_builder = builder.BagBuilder()

    # Attempt to make a bag
    bad_bag = test_builder.make_bag(
        src=IE_dir,
        bag_info=EXAMPLE_BAG_INFO.copy()
    )

    # Test_Assert
    assert bad_bag is None
    assert len(test_builder.log[Context.ERROR]) > 0

    # Test_Cleanup
    # Delete the folders
    rmtree(IE_dir)


def test_make_bag_additional_root_folder(
    example_dir=FIXTURES_DIR / TEST_IE_SUBDIR
):
    """
    Test making a bag from a directory with an additional root folder
    """

    # Copy IE_dir to keep the test data
    IE_dir = TESTING_DIR / TEST_IE_SUBDIR
    copy_directory(
        source_path=example_dir,
        dest_path=IE_dir,
        keep_source=True
    )

    # Add a root folder
    (IE_dir / "some_data").mkdir(parents=True, exist_ok=True)

    # Initiate the BagBuilder
    test_builder = builder.BagBuilder()

    # Attempt to make a bag
    bad_bag = test_builder.make_bag(
        src=IE_dir,
        bag_info=EXAMPLE_BAG_INFO.copy()
    )

    # Test_Assert
    assert bad_bag is None
    assert len(test_builder.log[Context.ERROR]) > 0

    # Test_Cleanup
    # Delete the folders
    rmtree(IE_dir)
