"""
This is a base class/classes for providing a standard set of attribute on Files/Folders.

- Comparison operators
- Registrar based hash
-

"""

import logging
import os
import platform
import re

from datetime import datetime
from filecmp import cmp
from functools import cached_property
from pathlib import Path
from shutil import copyfile
from typing import List, Dict, Optional, TypeVar, Union
from PIL import Image, UnidentifiedImageError

import piexif

logger = logging.getLogger('Cleaner')  # pylint: disable=invalid-name


IMAGE_FILES = ['.JPG', '.HEIC', '.AVI', '.MP4', '.THM', '.RTF', '.PNG', '.JPEG', '.MOV', '.TIFF']
SMALL_IMAGE = 360  # If width and height are less then this, it is thumb nail or some other derived file.

CT = TypeVar("CT", bound="Cleaner")  # pylint: disable=invalid-name
FileCT = TypeVar("FileCT", bound="FileCleaner")  # pylint: disable=invalid-name
ImageCT = TypeVar("ImageCT", bound="ImageCleaner")  # pylint: disable=invalid-name
FolderCT = TypeVar("FolderCT", bound="FolderCleaner")  # pylint: disable=invalid-name

# A couple of caches
duplicate_hash: Dict[str, List[CT]] = {}  # This hash is used to store processed files
folders: Dict[str, FolderCT] = {}  # This is used to store folders
root_path_list: List[str] = []  # some folders we have to ignore for folder comparisons


# Inter-instance data
PICTURE_FILES = ['.jpg', '.jpeg', '.tiff', '.tif', '.png', '.bmp', '.heic']
MOVIE_FILES = ['.mov', '.avi', '.mp4']


def file_cleaner(file: Path, folder: Optional[FolderCT]) -> Union[FileCT, ImageCT, FolderCT]:
    """
    shortcut for making Cleaner Objects
    :param file:
    :param folder:
    :return:
    """
    if file.is_dir():
        key = str(file)

        if key not in folders:
            folders[key] = FolderCleaner(file, parent=folder)
        return folders[key]
    suffix = file.suffix.lower()
    if suffix in PICTURE_FILES or suffix in MOVIE_FILES:

        return ImageCleaner(file, folder)

    return FileCleaner(file, folder)


class Cleaner:
    """
    A class to encapsulate the Path object that is going to be cleaned
    """
    def __init__(self, path_entry: Path, folder: FileCT = None):

        self.path = path_entry
        self.folder = folder
        self._date = None
        self.explicit_date = False

    def __eq__(self, other) -> bool:
        # Ensure you test that self.path.name == other.path.name and self.__class__ == other.__class__
        raise NotImplementedError

    def __lt__(self, other) -> bool:
        raise NotImplementedError

    def __gt__(self, other) -> bool:
        raise NotImplementedError

    def __ne__(self, other) -> bool:
        return not self == other

    def convert(self, work_dir: Path, migrated_base: Optional[Path], remove: bool = True) -> ImageCT:  # pylint: disable=unused-argument
        """
        Stub for converting,  only one type now but who knows
        :param work_dir:
        :param migrated_base:
        :param remove:
        :return:
        """
        return self  # If required and successful return new Cleaner subclass object / vs self

    @staticmethod
    def get_hash():
        """
        Used to post process after imports
        :return:
        """
        return duplicate_hash  # pragma: no cover

    @property
    def date(self) -> Optional[datetime]:
        """
        the date of an object
        :return:
        """
        raise NotImplementedError

    @property
    def is_small(self) -> bool:
        """
        Basically a test for garbage files
        :return:
        """
        raise NotImplementedError

    @property
    def is_valid(self) -> bool:
        """
        A way to define and enhance a good file
        :return:
        """
        return self.path.is_file() and self.path.stat().st_size != 0

    @cached_property
    def registry_key(self) -> str:
        """
        Common key based on name,  cached for performance
        :return:
        """
        target = self.path.stem.upper()
        parsed = re.match('(.+)_[0-9]{1,2}$', target)
        if parsed:
            target = parsed.groups()[0]
        return target

    def register(self, deep=True):
        """
        Register the existence of a file
        :return:
        """
        if self.is_registered(by_path=True, by_file=deep):
            logger.error('Trying to re_register %s', self.path)
        else:
            key = self.registry_key
            if key not in duplicate_hash:
                duplicate_hash[key] = []
            duplicate_hash[key].append(self)

    def de_register(self, silent=False):
        """
        Remove yourself from the the list of registered FileClean objects
        """
        if not self.is_registered(by_path=True):
            if not silent:
                logger.error('Trying to remove non-existent %s from duplicate_hash', self.path)
        else:
            new_list = []
            for value in duplicate_hash[self.registry_key]:
                if not value == self or not value.path.parent == self.path.parent:
                    new_list.append(value)
            if not new_list:
                del duplicate_hash[self.registry_key]
            else:
                duplicate_hash[self.registry_key] = new_list

    def is_registered(self, by_name: bool = True, by_path: bool = False, by_file: bool = False,
                      alternate_path: Path = None) -> bool:
        """
        Test for existing of a file
        :param by_name:
        :param by_path:
        :param by_file:
        :param alternate_path:
        :return:
        """
        value = self.get_registered(by_name=by_name, by_file=by_file, by_path=by_path, alternate_path=alternate_path)
        if value:
            return True
        return False

    def get_all_registered(self) -> List[FileCT]:
        """
        return a list of any Cleaner objects that match the name of this object.   If an item has been rolled over
        it will have a _:digit" suffix on the name.   We will find those too
        :return: List of FileCT objects (perhaps empty)
        """
        if self.registry_key in duplicate_hash:
            return duplicate_hash[self.registry_key]
        return []

    def get_registered(self, by_name: bool = True, by_path: bool = False, by_file: bool = False,
                       alternate_path: Path = None) \
            -> Optional[FileCT]:
        """

        :param by_name: bool : True - must match on the filename (upper cased)
        :param by_path: bool : False - the parent directory must match (or the alternate) - see below
        :param by_file: bool : False - the files must be exactly the same (as defined by types compare)
        :param alternate_path: None - If provided look for me in this path instead of the path I am in
        :return:
        """

        key = self.registry_key
        new_path = alternate_path if alternate_path else self.path.parent
        if key in duplicate_hash:
            for entry in duplicate_hash[key]:
                found_name = self.path.name.upper() == entry.path.name.upper() if by_name else True
                found_path = str(entry.path.parent) == str(new_path) if by_path else True

                if by_file:
                    found_file = self == entry
                else:
                    found_file = True
                if found_name and found_path and found_file:
                    return entry
        return None

    # File manipulation

    def relocate_file(self,
                      new_path: Path,
                      remove: bool = False,
                      rollover: bool = True,
                      register: bool = False):
        """
        :param new_path: A string representation of the folder
        :param remove: A boolean (default: False) Once successful on the relocate,   remove the original
        :param rollover: A boolean (default: True) rollover an existing file if it exists otherwise ignore
        :param register: A boolean (default:False), register this value after the move
        directory does not exist abort!
        :return:
        """

        new = None
        if new_path:
            if not new_path.exists():
                os.makedirs(new_path)
            new = new_path.joinpath(self.path.name)
            if self.path == new:
                logger.debug('Will not copy to myself %s', new)
                return
            if new.exists() and rollover:
                logger.debug('Rolling over %s', new)
                self.rollover_name(new)
            else:
                logger.debug('Will not overwrite %s', new)
            copyfile(str(self.path), new)

        if remove:
            try:
                self.de_register(silent=True)
                os.unlink(self.path)
            except OSError as error:
                logger.debug('%s could not be removed (%s)', self.path, error)

        if register and new:
            self.path = new
            self.folder = file_cleaner(new_path, None)
            self.register()

    def get_date_from_path_name(self) -> Optional[datetime]:
        """
        Check the file name for an embedded time stamp
        :return: datetime or None
        """
        parser_values = [  # Used to loop over _get_date_from_path_name
            ['^([0-9]{8}).([0-9]{6}).*$', '%Y%m%d', 1],
            ['^([0-9]{4}).([0-9]{1,2}).([0-9]{1,2}).*', '%Y%m%d', 3],
            ['^([0-9]{1,2}).([a-zA-Z]{3}).([0-9]{4}).*', '%d%b%Y', 3],
            ['^([0-9]{4}).([0-9]{1,2})[^0-9].*', '%Y%m', 2],
            ['^([0-9]{4}).[^0-9].*', '%Y', 1]
        ]

        def _get_date_from_path_name(regexp: str, date_format: str, array_max: int) -> Optional[datetime]:
            """
            Actual working part.

            :param regexp:
            :param date_format:
            :param array_max:
            :return:
            """
            re_parse = re.match(regexp, self.path.stem)
            if re_parse:
                re_array = re_parse.groups()
                date_string = "".join(re_array[0:array_max])
                try:
                    return datetime.strptime(date_string, date_format)
                except ValueError:  # pragma: no cover
                    logger.debug('Could not convert %s of %s to a date', date_string, self.path.name)
            return None

        for exp, fmt, index in parser_values:
            value = _get_date_from_path_name(exp, fmt, index)
            if value:
                return value
        return None

    def get_date_from_folder_names(self) -> Optional[datetime]:  # pylint: disable=inconsistent-return-statements
        """
        Maybe not the best way but this need to work on the folder part if it is a file vs an actual folder
        :return:
        """
        if self.__class__.__name__ != 'FolderCleaner':
            parent = str(self.path.parent.as_posix())
        else:
            parent = str(self.path.as_posix())

        parse_tree = re.match('.*([0-9]{4}).([0-9]{1,2}).([0-9]{1,2})$', parent)
        if parse_tree:
            try:
                return datetime(int(parse_tree.groups()[0]), int(parse_tree.groups()[1]), int(parse_tree.groups()[2]))
            except ValueError:
                return

        parse_tree = re.match('.*([0-9]{4}).([0-9]{1,2})$', parent)
        if parse_tree:
            try:
                return datetime(int(parse_tree.groups()[0]), int(parse_tree.groups()[1]), 1)
            except ValueError:
                return

        # match on last folder and name  /a/b/c/d/e.f -> /d/e.f
        parent_child = str(
            Path('/').joinpath(self.path.parts[len(self.path.parts) - 2]).joinpath(self.path.name).as_posix())

        parse_tree = re.match('^/([1-9][0-9]{3}).*/[A-Za-z0-9].+$', parent_child)
        if parse_tree:
            return datetime(int(parse_tree.groups()[0]), 1, 1)
        return

    @staticmethod
    def rollover_name(destination: Path):
        """
        Allow up to 20 copies of a file before removing the oldest
        file.type
        file_0.type
        file_1.type
        etc
        :return:
        """
        if destination.exists():
            for increment in reversed(range(20)):  # 19 -> 0
                old_path = destination.parent.joinpath(f'{destination.stem}_{increment}{destination.suffix}')
                new_path = destination.parent.joinpath(f'{destination.stem}_{increment + 1}{destination.suffix}')
                if old_path.exists():
                    os.rename(old_path, new_path)
            os.rename(destination, destination.parent.joinpath(f'{destination.stem}_0{destination.suffix}'))

    @classmethod
    def clear_caches(cls):
        """
        Get rid of all that cheesy persistent class data
        :return:
        """
        while root_path_list:
            root_path_list.pop()
        duplicate_hash.clear()

    @classmethod
    def add_to_root_path(cls, some_path: Path):
        """
        Root path is used to limit scope of recursive searching
        :param some_path:
        :return:
        """
        path = str(some_path)
        if path not in root_path_list:
            root_path_list.append(path)

    @classmethod
    def _get_root_path(cls):
        """
        just for debugging and testing
        :return:
        """
        return root_path_list  # pragma: no cover


class FileCleaner(Cleaner):

    """
    A class to encapsulate the regular file Path object that is going to be cleaned
    """

    def __init__(self, path_entry: Path, folder: Cleaner = None):
        super().__init__(path_entry, folder)

    def __eq__(self, other: FileCT):
        """
        Compare non-image files
        :param other:
        :return:
        """
        return cmp(self.path, other.path, shallow=False)

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        if self == other:  # Our files are the same
            if self.folder == other.folder:
                return self.date < other.date
        return False

    def __gt__(self, other):
        if self == other:
            return self.date > other.date
        return False

    @property
    def is_small(self):
        return False

    @property
    def date(self):
        """
        Should we consider path dates?
        :return:
        """
        if not self._date:
            if self.folder and self.folder.date:
                self._date = self.folder.date
            if not self._date:
                self._date = datetime.fromtimestamp(int(os.stat(self.path).st_mtime))
        return self._date


class ImageCleaner(Cleaner):
    """
    A class to encapsulate the image file Path object that is going to be cleaned
    """
    CONVERSION_SUFFIX = ['.HEIC', ]

    def __init__(self, path_entry: Path, folder: FolderCT = None):
        super().__init__(path_entry, folder)

        self._image = None
        self._image_data = []

    def __eq__(self, other: ImageCT):
        """
        Use the image data to compare images
        :param other: The other end of equal
        :return:
        """
        if self.__class__ == other.__class__:
            if self.path.name == other.path.name and os.stat(self.path).st_size == os.stat(other.path).st_size:
                return True
            # Try the hard way
            self.load_image_data()
            other.load_image_data()
            return self._image_data == other._image_data
        return False

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        # With images, a later time stamp is less of a file
        if self == other:
            if self.date and not other.date:
                return False
            if not self.date and other.date:
                return True
            if self.date and other.date:
                return self.date > other.date
        return False

    def __gt__(self, other):
        # With images,  a lesser timestamp is more of a file
        if self == other:
            if self.date and not other.date:
                return True
            if not self.date and other.date:
                return False
            if self.date and other.date:
                return self.date < other.date
        return False

    @property
    def is_small(self):
        opened = False
        small = False
        if not self._image:
            self.open_image()
            opened = True
        if self._image:
            if self._image.width <= SMALL_IMAGE and self._image.height <= SMALL_IMAGE:
                small = True
        if opened:
            self.close_image()
        return small

    @property
    def date(self):
        if not self._date:
            self._date = self.get_date_from_image()
            if not self._date:  # Short circuit to find a date
                self._date = self.get_date_from_path_name() or self.get_date_from_folder_names()
                if not self._date and self.folder:
                    self._date = self.folder.date
            #    if self._date:
            #        self.update_image()
        return self._date

    # Ensure we have a date for the existing image

    def close_image(self):
        """
        Close image file
        :return:
        """
        if self._image:
            self._image.close()
        self._image = None

    def open_image(self):
        """
        Open image file
        :return:
        """
        if not self._image:
            try:
                self._image = Image.open(self.path)
            except UnidentifiedImageError as error:
                logger.debug('open_image UnidentifiedImageError %s - %s', self.path, error.strerror)
            except OSError as error:
                logger.debug('open_image OSError %s - %s', self.path, error.strerror)
        return self._image

    def load_image_data(self):
        """
        Load the image data,  actual picture not metadata
        :return:
        """
        opened = False
        if not self._image_data:
            if not self._image:
                self.open_image()
                opened = True
            if self._image:
                try:
                    for val in self._image.getdata().split():
                        self._image_data.append(val.histogram())
                except OSError:  # pragma: no cover
                    logger.error('Warning - failed to read image: %s', self.path)
                    self._image = None
        if opened:
            self.close_image()

    @property
    def image_data(self):
        """
        Load image date and return as an element
        :return:
        """
        self.load_image_data()
        return self._image_data

    def convert(self, work_dir: Path, migrated_base: Optional[Path], remove: bool = True) -> ImageCT:
        """
        Convert HEIC files to jpg files.   Do the conversion in the run_path since we shouldn't update existing dir.

        if migration_base:
            move original file to this path (removes original)
        else
            if in_place:
                remove it
            else:
                leave it

        :param work_dir: Working directory to store temporary working files
        :param migrated_base:  Where (if any) to archive originals to
        :param in_place: default: True,  remove this file

        :return: self or a new object that's updated

        I think this also works with HEIC files
        """
        if self.path.suffix.upper() not in self.CONVERSION_SUFFIX:
            return self

        if platform.system() == 'Windows':
            logger.error('Conversion from HEIC is not supported on Windows')
            return self

        import pyheif  # pylint: disable=import-outside-toplevel, import-error

        original_name = self.path
        new_name = work_dir.joinpath(f'{self.path.stem}.jpg')

        if new_name.exists():
            new_name.unlink()
            logger.debug('Cleaning up %s - It already exists', new_name)

        exif_dict = None
        heif_file = pyheif.read(original_name)
        image = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw", heif_file.mode, heif_file.stride)
        try:
            for metadata in heif_file.metadata or []:
                if 'type' in metadata and metadata['type'] == 'Exif':
                    exif_dict = piexif.load(metadata['data'])
            if exif_dict:
                exif_bytes = piexif.dump(exif_dict)
                image.save(new_name, format("JPEG"), exif=exif_bytes)
                if migrated_base:
                    self.relocate_file(migrated_base, remove=remove, rollover=False)
                elif remove:
                    original_name.unlink()
                return ImageCleaner(Path(new_name), self.folder)
        except AttributeError as error:  # pragma: no cover
            logger.error('Conversion error: %s - Reason %s is no metadata attribute', self.path, error)
        return self  # pragma: no cover

    def get_date_from_image(self) -> Union[datetime, None]:  # pylint: disable=inconsistent-return-statements
        """
        Given an Image object,  attempt to extract the date it was take at
        :return: datetime
        """

        image_date = None
        try:
            exif_dict = piexif.load(str(self.path))

            if exif_dict:
                try:
                    image_date = exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal]
                except KeyError:
                    try:
                        image_date = exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized]
                    except KeyError:
                        try:
                            image_date = exif_dict['0th'][piexif.ImageIFD.DateTime]
                        except KeyError:
                            pass

            if image_date:
                try:
                    date_value, _ = str(image_date, 'utf-8').split(' ')
                    return datetime.strptime(date_value, '%Y:%m:%d')
                except ValueError:  # pragma: no cover
                    logger.debug('Corrupt date data %s', self.path)  # pragma: no cover
            else:
                logger.debug('Could not find a date in %s', self.path)

        except piexif.InvalidImageDataError:
            logger.debug('Failed to load %s - Invalid JPEG/TIFF', self.path)
        except FileNotFoundError:
            logger.debug('Failed to load %s - File not Found', self.path)


class FolderCleaner(Cleaner):
    """
    A class for processing folders
    path_entry is a Path we are processing
    root_folder is the Path of the input folder tree  (value is cached)
    parent,  the FolderCleaner object we are from.

    """

    # pylint: disable=too-many-arguments
    def __init__(self, path_entry: Path,
                 root_folder: Path = None,
                 output_folder: Path = None,
                 parent: FolderCT = None,
                 app_name: str = None):

        super().__init__(path_entry, parent)

        if root_folder and str(root_folder) not in root_path_list:
            root_path_list.append(str(root_folder))

        if output_folder and str(output_folder) not in root_path_list:
            root_path_list.append(str(output_folder))

        self.description: Optional[str] = self.get_description_from_path(app_name)
        self.parent: Optional[FolderCT] = parent

    def __eq__(self, other):
        # Comparison is based first on custom folder (vs just arbitrary dates)
        if self.custom_folder and other.custom_folder:
            return True
        if self.date and other.date:
            return True
        return False

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        if not self == other:
            if self.custom_folder:
                return False
            if other.custom_folder:
                return True
            if self.date:
                return False
            if other.date:
                return True
        return False

    def __gt__(self, other):
        if not self == other:
            if self.custom_folder:
                return True
            if other.custom_folder:
                return False
            if self.date:
                return True
            if other.date:
                return False
        return False

    @property
    def size(self):
        """
        Number of direct elements
        :return:
        """
        count = 0
        for _ in self.path.iterdir():
            count += 1
        return count

    @property
    def is_small(self):
        """
        artibraty small is 10
        :return:
        """
        return self.size < 10

    @cached_property
    def custom_folder(self) -> bool:
        """
        A utility to test if the folder was explicitly named (thus custom)

        A custom folder is a folder that does not end with a date format YYYY/MM/DD and is not a folder from the root
        path list.
        :return: boolean  - True if a custom folder

        .../2012/3/3/foobar is custom
        .../foo/bar is NOT custom
        .../2012/3/3 is NOT managed
        .../foobar/2012/3/3 ??? should this be custom
        """

        folder = str(self.path)
        if not re.match('.*[0-9]{4}.[0-9]{1,2}.[0-9]{1,2}$', folder):
            if folder not in root_path_list:
                if self.description:
                    return True
        return False

    @property
    def date(self) -> Optional[datetime]:
        if not self._date:
            if not (len(self.path.name) == 22 and self.path.name.find(' ') == -1):  # Get rid of garbage first
                self._date = self.get_date_from_path_name() or self.get_date_from_folder_names()   # short circuit

        if not self._date and self.folder:
            self._date = self.folder.date  # This is recursive
            # Use the parent date
        return self._date

    def get_description_from_path(self, app_name) -> Optional[str]:
        """
        All of these paths have September 27th, 1961 as the date.

        pictures/1961/9/27
        pictures/2014/1961/09/27
        pictures/1961_9_27_Roxy5
        pictures/1961-09-27 Murphys Point
        pictures/1961_9_Sara
        pictures/2961 - Camping
        pictures/2014/2014/06/30/19610927-063739/zCMlYzsaTqyElbmIFHvvLw
        pictures/2014/2014/06/30/19610927-063736
        pictures/1961_09_27_TriptoFalls
        pictures/27-Sep-1961

        :return:
        """
        parser_values = [
            '^[0-9]{4}.[0-9]{1,2}.[0-9]{1,2}(.*)',
            '^[0-9]{2}.[a-zA-Z]{3}.[0-9]{4}(.*)',
            '^[0-9]{4}.[0-9]{1,2}(.*)',
            '^[0-9]{4}(.*)',
        ]

        # We have a lot of paths that were generated by some other import
        if len(self.path.name) == 22 and self.path.name.find(' ') == -1:
            return None
        if re.match('^[0-9]{8}-[0-9]{6}$', self.path.name):  # Pure Date
            return None
        if app_name and self.path.name.startswith(app_name):
            return None

        try:
            int(self.path.name)
            return None  # Pure date path
        except ValueError:
            pass

        description = None
        matched = False
        for exp in parser_values:
            re_parse = re.match(exp, self.path.name)
            if re_parse:
                description = re_parse.groups()[0]
                matched = True
                break

        if not description and not matched:
            description = self.path.name

        if description:  # Cleanup some junk
            parts = re.match('^([-_ ]*)(.*)', description)
            description = parts.groups()[1]

        return description if description != '' else None

    def recursive_description_lookup(self, current_description: Union[Path, None], to_exclude: List[str]) -> str:
        """
        Recurse your folders to build up path based on descriptive folder names
        ..../foo/bar/foobar/my.file
        :param current_description:  a string with the build up path
        :param to_exclude: an array of path components that we don't want to include in description tree

        :return: a string with the path name based on os.path.sep and the various folder levels
        """
        if self.description:
            if self.description not in to_exclude:
                if current_description:
                    current_description = Path(self.description).joinpath(current_description)
                else:
                    current_description = Path(self.description)
        if self.folder:
            current_description = self.folder.recursive_description_lookup(current_description, to_exclude)
        return current_description

    @staticmethod
    def reset():
        """
        clear the global root_path_list
        :return:
        """
        while root_path_list:
            root_path_list.pop()
