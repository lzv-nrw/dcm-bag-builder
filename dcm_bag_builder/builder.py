"""
This module defines a BagBuilder-class which serves as a wrapper for the
functionality of the python bagit-library (LOC).
"""


from typing import Optional
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from shutil import copytree, rmtree

import bagit

from dcm_common.util import list_directory_content, make_path
from dcm_common import LoggingContext as Context, Logger


# Set default checksums
DEFAULT_CHECKSUMS = bagit.DEFAULT_CHECKSUMS.copy()
# Set BagIt-Version
BAGIT_VERSION = "1.0"


class BagBuilder():
    """
    This class has two methods that build a bag based on the make_bag
    method from the bagit library. The bag object is represented by the
    Bag(bag_dir) class from the bagit library.

    Optional arguments:
    manifests -- a list of the algorithms to be used for the manifest
                 files when creating bags
                 (default None -> leads to DEFAULT_CHECKSUMS).
    tagmanifests -- a list of the algorithms to be used for the tag-
                    manifest files when creating bags
                    (default None -> leads to DEFAULT_CHECKSUMS).
    """

    BUILDER_TAG = "Bag Builder"

    def __init__(
        self,
        manifests: Optional[list[str]] = None,
        tagmanifests: Optional[list[str]] = None
    ) -> None:
        # Setup log
        self.log = Logger(default_origin=self.BUILDER_TAG)

        # Set the manifests
        if manifests is None:
            self.manifests = DEFAULT_CHECKSUMS
        else:
            self.manifests = manifests

        self.log.log(
            Context.INFO,
            body=f"Using algorithms {self.manifests} for manifest generation."
        )

        # Set the tagmanifests
        if tagmanifests is None:
            self.tagmanifests = DEFAULT_CHECKSUMS
        else:
            self.tagmanifests = tagmanifests

        self.log.log(
            Context.INFO,
            body=f"Using algorithms {self.tagmanifests} for tag-manifest "
                + "generation."
        )

        # The bagit library does not support individual settings for manifests
        # and tag-manifests. This is, however, included in the DCM-
        # specification. Consequently, the union of both sets of algorithms is
        # used during bag-creation and unwanted files/entries in the tag-
        # manifests are removed afterwards
        # set the used algorithms as the union of manifests and tagmanifests
        self._checksums = list(set().union(self.manifests, self.tagmanifests))

    def _get_bag_creation_time(self) -> str:
        """
        Return the current time according to the format YYYY-MM-DDThh:mm:ssTZD,
        as defined in the LZV.nrw BagIt specifications.

        Example: 2023-04-03T13:37:00+02:00
        """
        # Get the UTC time
        utc_dt = datetime.now(timezone.utc)
        # Get the local time
        local_time = utc_dt.astimezone()
        # Get the UTC offset in the form +HHMM or -HHMM.
        time_zone_str = local_time.strftime("%z")
        # Adapt the time_zone_str
        time_zone_separator_index = 3
        time_zone_str = (
            time_zone_str[:time_zone_separator_index]
            + ":"
            + time_zone_str[time_zone_separator_index:]
        )
        # Get the creation time
        creation_time = (
            local_time.strftime("%Y-%m-%d")
            + "T"
            + local_time.strftime("%H:%M:%S")
            + time_zone_str
        )
        return creation_time

    def _call_bagit(
        self,
        src: Path,
        bag_info: Optional[dict[str, str | list[str]]] = None,
        processes: int = 1,
        encoding: str = "utf-8"
    ) -> Optional[bagit.Bag]:
        """
        Make a bag from a directory.

        On success it returns the a bagit.Bag-instance.
        If the basic bag validation fails, it returns None.

        This internal method uses the make_bag method from the bagit library.
        https://github.com/LibraryOfCongress/bagit-python/blob/ed81c2384955747e8ba9dcb9661df1ac1fd31222/bagit.py#L144

        Keyword arguments:
        src -- path to an IE (containing "data" and optionally "meta")
        bag_info -- selected subset of metadata to be added to the
                    bag-info.txt; input is a dictionary with either strings
                    or lists of strings in its values
                    (default None)
        processes -- number of threads for generating file checksums
                     (see bagit library)
                     (default 1)
        encoding -- encoding for writing and reading manifest files
                    (see bagit library)
                    (default "utf-8")
        """

        # Make the bag
        data_dir = src / "data"
        meta_dir = src / "meta"
        bag = bagit.make_bag(
            # bag_dir cannot be a Path object, due to the bagit library.
            bag_dir=str(data_dir),
            bag_info=bag_info,
            processes=processes,
            checksums=self._checksums,
            checksum=None,
            encoding=encoding
        )

        # Override the file bagit.txt to set the BagIt-Version
        # This approach imitates the original creation of the file in the bagit library
        # https://github.com/LibraryOfCongress/bagit-python/blob/ed81c2384955747e8ba9dcb9661df1ac1fd31222/bagit.py#L246
        txt = (
            f"BagIt-Version: {BAGIT_VERSION}\n"
            f"Tag-File-Character-Encoding: {encoding.upper()}\n"
        )
        bagit_file_path = Path(data_dir) / "bagit.txt"
        Path(bagit_file_path).write_text(txt, encoding=encoding)
        # bag.version_info will be updated after opening the Bag with bagit.Bag()
        # https://github.com/LibraryOfCongress/bagit-python/blob/ed81c2384955747e8ba9dcb9661df1ac1fd31222/bagit.py#L350C37-L350C37

        # Update the bag info
        # from bagit library: You can change the metadata
        # persisted to the bag-info.txt by using the info property on a Bag.
        bag = bagit.Bag(str(data_dir))
        # Generate the field Bagging-DateTime
        bag.info["Bagging-DateTime"] = self._get_bag_creation_time()
        # Delete the field Bagging-Date
        if "Bagging-Date" in bag.info:
            del bag.info["Bagging-Date"]
        # Save the bag without regenerating manifests
        bag.save(processes=processes, manifests=False)

        if meta_dir.is_dir():
            # Add the metadata folder into the bag
            copytree(src=meta_dir, dst=data_dir / "meta")
            rmtree(meta_dir)
            # Save the bag and regenerate manifests
            # The save method from the bagit library recalculates the Payload-Oxum
            # (from the bag payload, i.e. all files/folders in the data folder)
            # and regenerates the manifest files when manifests=True
            # (in this step it is expected that the files
            # from the meta folder are added - which do NOT belong in the bag payload).
            bag.save(processes=processes, manifests=True)

        # Perform the basic validation routine from the bagit library
        if bag.is_valid(fast=False, completeness_only=False):
            return bag

        return None

    def _get_output_path(
        self, base_path: Path, max_retries: int = 10
    ) -> Optional[Path]:
        """
        Create a new random new directory in `base_path`.

        Returns a `Path` to that directory. Returns `None` if
        `max_retries` is exceeded.

        Keyword arguments:
        base_path -- base path in which to search for non-existent
                     directory
        """
        for _ in range(max_retries):
            try:
                (output := base_path / str(uuid4())).mkdir(exist_ok=False)
            except FileExistsError:
                pass
            else:
                return output
        return None

    def _validate_ie(self, src: Path) -> bool:
        """Validate src-directory structure/contents."""
        if not (src / "data").is_dir():
            self.log.log(
                Context.ERROR,
                body="Source IE does not follow specification. "
                    + "Missing 'data' directory."
            )
            return False
        bad_contents = [
            str(p) for p in list_directory_content(
                src,
                pattern="*",
                condition_function=lambda p:
                    p not in ((src / "data"), (src / "meta"))
            )
        ]
        if bad_contents:
            self.log.log(
                Context.ERROR,
                body="Source IE does not follow specification. "
                    + f"Problematic content: {bad_contents}."
            )
            return False
        return True

    def make_bag(
        self,
        src: str | Path,
        bag_info: dict[str, str | list[str]],
        dest: Optional[str | Path] = None,
        exist_ok: bool = False,
        processes: int = 1,
        encoding: str = "utf-8"
    ) -> Optional[bagit.Bag]:
        """
        Makes a bag from an intellectual entity (IE). Returns this bag
        on success, otherwise returns `None`.

        It expects an IE structure that conforms to the LZV.nrw
        specifications:
        INPUT
        <src>/
            ├── data/
            └── meta/ (optional)
        OUTPUT
        <output_path>/ (or <src>/)
            ├── data/
            ├── meta/ (optional)
            ├── bag-info.txt
            ├── bagit.txt
            ├── manifest-<checksum_abbreviation>.txt (multiple txt files)
            └── tagmanifest-<checksum_abbreviation>.txt (multiple txt files)

        Keyword arguments:
        src -- path to the source directory of the IE
        bag_info -- selected subset of metadata to be added to the
                    bag-info.txt; input is a dictionary with either strings
                    or lists of strings in its values
        dest -- destination directory for the bag
                (default None; corresponds to building bag in-place)
        exist_ok -- if `False` and `dest` is not `None` and already
                    exists, a `FileExistsError` is raised
        processes -- number of threads for generating file checksums
                     (see bagit library)
                     (default 1)
        encoding -- encoding for writing and reading manifest files
                    (see bagit library)
                    (default "utf-8")
        """

        # Report: write the input directory
        self.log.log(
            Context.INFO,
            body=f"Making bag from '{str(src)}'."
        )

        # If src is a string, convert into path.
        src = make_path(src)

        # Validate the expected structure in src
        if not self._validate_ie(src):
            return None

        # check whether output is valid
        if dest is not None:
            Path(dest).mkdir(exist_ok=exist_ok)
        # find and prepare temporary output-dir
        _dest = self._get_output_path((make_path(dest) or src).parent)
        if _dest is None:
            self.log.log(
                Context.ERROR,
                body="Unable to generate output directory (maximum retries"
                    + " exceeded)."
            )
            return
        copytree(src, _dest, dirs_exist_ok=True)  # bagit works on copy of ie

        # Create the bag
        bag = self._call_bagit(
            src=_dest,
            bag_info=bag_info,
            processes=processes,
            encoding=encoding
        )

        # remove the tmp-data and exit if a problem has occurred
        if bag is None:
            rmtree(_dest)
            self.log.log(
                Context.ERROR,
                body="Initial bag validation failed (bagit.Bag.is_valid "
                    + "returned False)."
            )
            return

        # move result to dest
        if dest is None:
            rmtree(src)
            (_dest / "data").rename(src)
            bag = bagit.Bag(str(src))
        else:
            rmtree(dest)
            (_dest / "data").rename(dest)
            bag = bagit.Bag(str(dest))
        _dest.rmdir()

        # Delete the manifest files that were not required
        for excessive_alg in (set(self._checksums) - set(self.manifests)):
            mfile = src / Path("manifest-" + excessive_alg + ".txt")
            mfile.unlink()
        # Generate new tag-manifest files,
        # without generating new manifest files (-> manifests=False).
        bag.save(processes=processes, manifests=False)
        # Delete the tag-manifest files that were not required
        for excessive_alg in (set(self._checksums) - set(self.tagmanifests)):
            tag_mfile = src / Path("tagmanifest-" + excessive_alg + ".txt")
            tag_mfile.unlink()

        # Perform the basic validation routine from the bagit library
        if not bag.is_valid(fast=False, completeness_only=False):
            rmtree(_dest)
            self.log.log(
                Context.ERROR,
                body="Secondary bag validation failed (bagit.Bag.is_valid "
                    + "returned False)."
            )
            return

        # success
        self.log.log(
            Context.INFO,
            body="Successfully created bag."
        )

        return bag
