import logging
import os
import platform
import re

import piexif

from datetime import datetime
from filecmp import cmp
from functools import cached_property
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from shutil import copyfile
from tempfile import TemporaryDirectory
from typing import List, Dict, Optional, TypeVar, Union

logger = logging.getLogger('Cleaner')


IMAGE_FILES = ['.JPG', '.HEIC', '.AVI', '.MP4', '.THM', '.RTF', '.PNG', '.JPEG', '.MOV', '.TIFF']
SMALL_IMAGE = 360  # If width and height are less then this, it is thumb nail or some other derived file.

CT = TypeVar("CT", bound="Cleaner")
FileCT = TypeVar("FileCT", bound="FileCleaner")
ImageCT = TypeVar("ImageCT", bound="ImageCleaner")
FolderCT = TypeVar("FolderCT", bound="FolderCleaner")

# A couple of caches
duplicate_hash: Dict[str, List[CT]] = {}  # This hash is used to store processed files
root_path_list: List[str] = []  # some folders we have to ignore for folder comparisons


def file_cleaner(file: Path, folder: Optional[FolderCT]) -> Union[FileCT, ImageCT, FolderCT]:
    if file.is_dir():
        return FolderCleaner(file, parent=folder)
    if file.suffix.upper() in IMAGE_FILES:
        return ImageCleaner(file, folder)
    else:
        return FileCleaner(file, folder)


class Cleaner:

    os.environ.get("HOME")
    """
    A class to encapsulate the Path object that is going to be cleaned
    """

    # Inter-instance data
    PICTURE_FILES = ['.JPG', '.HEIC', '.THM', '.RTF', '.PNG', '.JPEG', '.TIFF']
    MOVIE_FILES = ['.MOV', '.AVI', '.MP4']

    all_images = []
    all_movies = []

    def __init__(self, path_entry: Path, folder: FileCT = None):

        if not self.all_images:
            for item in self.PICTURE_FILES:
                self.all_images.append(item.upper())
                self.all_images.append(item.lower())
            for item in self.MOVIE_FILES:
                self.all_movies.append(item.upper())
                self.all_movies.append(item.lower())

        self.path = path_entry
        self.folder = folder
        self._date = None

    def __eq__(self, other) -> bool:
        # Ensure you test that self.path.name == other.path.name and self.__class__ == other.__class__
        raise NotImplementedError

    def __lt__(self, other) -> bool:
        raise NotImplementedError

    def __gt__(self, other) -> bool:
        raise NotImplementedError

    def __ne__(self, other) -> bool:
        return not self == other

    def convert(self, work_dir: Path, migrated_base: Optional[Path], remove: bool = True) -> ImageCT:
        return self  # If required and successful return new Cleaner subclass object / vs self

    @staticmethod
    def get_hash():  # just for debugging
        return duplicate_hash  # pragma: no cover

    @property
    def date(self) -> Optional[datetime]:
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
        return self.path.is_file() and self.path.stat().st_size != 0

    @cached_property
    def registry_key(self) -> str:
        target = self.path.stem.upper()
        parsed = re.match('(.+)_[0-9]{1,2}$', target)
        if parsed:
            target = parsed.groups()[0]
        return target

    def de_register(self, silent=False):
        """
        Remove yourself from the the list of registered FileClean objects
        """
        if not self.is_registered(by_path=True):
            if not silent:
                logger.error(f'Trying to remove non-existent {self.path}) from duplicate_hash')
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

    def register(self):
        if self.is_registered(by_path=True, by_file=True):
            logger.error(f'Trying to re_register {self.path})')
        else:
            key = self.registry_key
            if key not in duplicate_hash:
                duplicate_hash[key] = []
            duplicate_hash[key].append(self)

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
                    logger.debug(f'Comparing {key} {entry.path} to {self.path}')
                    found_file = self == entry
                else:
                    found_file = True
                if found_name and found_path and found_file:
                    return entry
        return None

    def get_new_path(self, base: Union[Path, None], invalid_parents: List[str] = None) -> Optional[Path]:
        """
        Using the time stamp and current location/description build a folder path to where this
        file should be moved to.
        :param: base,  is the root folder to build the new path from
        :invalid_parents: A list of strings components that should be excluded from any new path
        :return:  A Path representing where this file should be moved or None, if the base path was None
        """

        if not base:
            return None

        if not invalid_parents:
            invalid_parents = []

        date = self.date if self.date else None
        description_path = None
        if self.folder:
            description_path = self.folder.recursive_description_lookup(None, invalid_parents)
            if not date:
                date = self.folder.date

        if not date and description_path:
            return base.joinpath(description_path)

        if not date:
            return base

        year = month = day = None
        # Bug... all folders have a time.
        if self.date:
            year = self.date.year
            month = self.date.month
            day = self.date.day

        new = base
        if year and description_path:
            new = base.joinpath(str(year)).joinpath(description_path)
        elif year:
            new = base.joinpath(str(year))
            if month:
                new = new.joinpath(str(month))
                if day:
                    new = new.joinpath(str(day))
        if not new.exists():
            os.makedirs(new)
        return new

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

            if new.exists() and rollover:
                logger.debug(f'Rolling over {new}')
                self.rollover_name(new)
            else:
                logger.debug(f'Will not overwrite {new}')
            copyfile(str(self.path), new)

        if remove:
            try:
                self.de_register(silent=True)
                os.unlink(self.path)
            except OSError as e:
                logger.debug(f'{self.path} could not be removed ({e}')

        if register and new:
            self.path = new
            self.register()

    def get_date_from_path_name(self) -> Optional[datetime]:
        """
        Check the file name for an embedded time stamp
        :return: datetime or None
        """
        parser_values = [  # Used to loop over _get_date_from_path_name
            ['^([0-9]{8}).([0-9]{6}).*$', '%Y%m%d%H%M%S', 3],
            ['^([0-9]{4}).([0-9]{2}).([0-9]{2}).*', '%Y%m%d', 3],
            ['^([0-9]{2}).([a-zA-Z]{3}).([0-9]{4}).*', '%d%b%Y', 3],
            ['^([0-9]{4}).([0-9]{2}).+', '%Y%m', 2]
        ]

        def _get_date_from_path_name(regexp: str,  date_format: str, array_max: int) -> Optional[datetime]:
            re_parse = re.match(regexp, self.path.stem)
            if re_parse:
                re_array = re_parse.groups()
                date_string = "".join(re_array[0:array_max])
                try:
                    return datetime.strptime(date_string, date_format)
                except ValueError:  # pragma: no cover
                    logger.debug(f'Could not convert {date_string} of {self.path.name} to a date')
            return None

        for exp, fmt, index in parser_values:
            value = _get_date_from_path_name(exp, fmt, index)
            if value:
                return value
        return None

    def get_date_from_folder_names(self) -> Optional[datetime]:
        # Maybe not the best way but this need to work on the folder part if it is a file vs an actual folder
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
        parent_child = str(Path('/').joinpath(
            self.path.parts[len(self.path.parts)-2]).joinpath(
            self.path.name).as_posix())

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
        # todo: break out of this loop
        if os.path.exists(destination):
            basename = destination.name[:len(destination.name) - len(destination.suffix)]
            for increment in reversed(range(20)):  # 19 -> 0
                old_path = f'{destination.parent}{os.path.sep}{basename}_{increment}{destination.suffix}'
                new_path = f'{destination.parent}{os.path.sep}{basename}_{increment + 1}{destination.suffix}'
                if os.path.exists(old_path):
                    os.rename(old_path, new_path)
            os.rename(destination, f'{destination.parent}{os.path.sep}{basename}_0{destination.suffix}')

    @classmethod
    def clear_caches(cls):
        while root_path_list:
            root_path_list.pop()
        duplicate_hash.clear()

    @classmethod
    def add_to_root_path(cls, some_path: Path):
        path = str(some_path)
        if path not in root_path_list:
            root_path_list.append(path)

    @classmethod
    def get_root_path(cls):  # just for debugging
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
        # todo: This might be very slow
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

        self._image = None  # todo: Real image time > then name/dir time.  Maybe stop updating image time.
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
        if self._image:
            self._image.close()
        self._image = None

    def open_image(self):
        if not self._image:
            try:
                self._image = Image.open(self.path)
            except UnidentifiedImageError as e:
                logger.debug(f'open_image UnidentifiedImageError {self.path} - {e.strerror}')
            except OSError as e:
                logger.debug(f'open_image OSError {self.path} - {e.strerror}')
        return self._image

    def load_image_data(self):
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
                    # todo: Find a way to valid this.    OSError does not seem correct
                    logger.error(f'Warning - failed to read image: {self.path}')
                    self._image = None
        if opened:
            self.close_image()

    @property
    def image_data(self):
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
        #  todo: Try this on HEIC files
        if self.path.suffix.upper() not in self.CONVERSION_SUFFIX:
            return self

        if platform.system() == 'Windows':
            logger.error('Conversion from HEIC is not supported on Windows')
            return self
        else:
            import pyheif

        original_name = self.path
        new_name = work_dir.joinpath(f'{self.path.stem}.jpg')

        if new_name.exists():
            new_name.unlink()
            logger.debug(f'Cleaning up {new_name} - It already exists')

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
                # todo:  Another bug,   we loose path info on the converted file
                if migrated_base:
                    self.relocate_file(self.get_new_path(base=migrated_base), remove=remove, rollover=False)
                elif remove:
                    original_name.unlink()
                return ImageCleaner(Path(new_name), self.folder)
        except AttributeError as e:  # pragma: no cover
            # todo: Try and find a real case where this is true
            logger.error(f'Conversion error: {self.path} - Reason {e} is no metadata attribute')
        return self  # pragma: no cover

    """
    def update_image(self):
        '''
        Update an image file with the data provided
        :return: None
        '''
        changed = False
        try:
            exif_dict = piexif.load(str(self.path))
            logger.debug(f'Update Image - success loading {self.path}')
            if self._date:
                changed = True
                new_date = self._date.strftime("%Y:%m:%d %H:%M:%S")
                exif_dict['0th'][piexif.ImageIFD.DateTime] = new_date
                exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = new_date
                exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = new_date
            if changed:
                try:
                    exif_bytes = piexif.dump(exif_dict)
                    piexif.insert(exif_bytes, str(self.path))
                except ValueError as e:  # pragma: no cover
                    logger.error(f'Failed to update {self.path} Error {e}')
        except piexif.InvalidImageDataError:  # pragma: no cover
            logger.debug(f'Failed to load {self.path} - Invalid JPEG/TIFF')
        except FileNotFoundError:  # pragma: no cover
            logger.error(f'Failed to load {self.path} - File not Found')
    """

    def get_date_from_image(self):
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
                    logger.debug(f'Corrupt date data {self.path}')  # pragma: no cover
            else:
                logger.debug(f'Could not find a date in {self.path}')

        except piexif.InvalidImageDataError:
            logger.debug(f'Failed to load {self.path} - Invalid JPEG/TIFF')
        except FileNotFoundError:
            logger.debug(f'Failed to load {self.path} - File not Found')


class FolderCleaner(Cleaner):
    """
    A class for processing folders
    path_entry is a Path we are processing
    root_folder is the Path of the input folder tree  (value is cached)
    parent,  the FolderCleaner object we are from.

    """

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
                return True
        return False

    @cached_property
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
        - pictures/2021/10/11
        - pictures/2014/2014/06/30
        pictures/2004_04_17_Roxy5
        pictures/2016-09-25 Murphys Point
        pictures/2003_10_Sara
        pictures/2016 - Camping
        pictures/Alex's House
        - pictures/2014/2014/06/30/20140630-063739/zCMlYzsaTqyElbmIFHvvLw
        - pictures/2014/2014/06/30/20140630-063736
        pictures/2003_04_06_TriptoFalls
        - pictures/12-Aug-2014

        :return:
        """
        parser_values = [
            '^[0-9]{4}.[0-9]{2}.[0-9]{2}(.*)',
            '^[0-9]{2}.[a-zA-Z]{3}.[0-9]{4}(.*)',
            '^[0-9]{4}.[0-9]{2}(.*)',
            '^[0-9]{4}(.*)',
        ]

        # We have a lot of they were generated by some other import
        if len(self.path.name) == 22 and self.path.name.find(' ') == -1:
            return None
        elif re.match('^[0-9]{8}-[0-9]{6}$', self.path.name):  # Pure Date
            return None
        elif app_name and self.path.name.startswith(app_name):
            return None
        else:
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
        while root_path_list:
            root_path_list.pop()
