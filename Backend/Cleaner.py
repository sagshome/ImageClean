import logging
import os
import pickle
import platform
import re

import piexif

from datetime import datetime
from filecmp import cmp
from functools import cached_property
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from shutil import copyfile
from typing import List, Dict, Optional, TypeVar, Union

logger = logging.getLogger('Cleaner')

NEW_FILE: int = 0
EXACT_FILE: int = 1
LESSER_FILE: int = 2
GREATER_FILE: int = 3
SMALL_FILE: int = 4

WARNING_FOLDER_SIZE = 100  # Used when auditing directories,  move then 100 members is a Yellow flag


IMAGE_FILES = ['.JPG', '.HEIC', '.AVI', '.MP4', '.THM', '.RTF', '.PNG', '.JPEG', '.MOV', '.TIFF']
SMALL_IMAGE = 360  # If width and height are less then this, it is thumb nail or some other derived file.

CT = TypeVar("CT", bound="Cleaner")
FileCT = TypeVar("FileCT", bound="FileCleaner")
ImageCT = TypeVar("ImageCT", bound="ImageCleaner")
FolderCT = TypeVar("FolderCT", bound="FolderCleaner")


def file_cleaner(file: Path, folder: Optional[FolderCT]) -> Union[FileCT, ImageCT, FolderCT]:
    if file.is_dir():
        return FolderCleaner(file, parent=folder)
    if file.suffix.upper() in IMAGE_FILES:
        return ImageCleaner(file, folder)
    else:
        return FileCleaner(file, folder)


class Cleaner:

    os.environ.get("HOME")
    CleanerCT = TypeVar("CleanerCT", bound="Cleaner")
    """
    A class to encapsulate the Path object that is going to be cleaned
    """

    duplicate_hash: Dict[str, List[CleanerCT]] = {}  # This hash is used to store processed files

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

    def clean_working_dir(self, folder: Path):
        for entry in folder.iterdir():
            if entry.is_dir():
                self.clean_working_dir(entry)
            else:
                if entry.suffix in self.all_images:
                    logger.debug(f'Cleaning up/deleting: {entry}')
                    entry.unlink()
                if entry.suffix in self.all_movies:
                    logger.debug(f'Cleaning up/deleting: {entry}')
                    entry.unlink()

    def convert(self, migrated_base: Path, run_path: Path, keep: bool = True, in_place: bool = True) -> CleanerCT:
        return self  # If required and successful return new Cleaner subclass object / vs self

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
        try:
            if self.path.is_file() and self.path.stat().st_size != 0:
                return True
        except FileNotFoundError:
            pass
        return False

    @cached_property
    def just_name(self) -> str:
        return self.path.stem

    @property
    def just_path(self) -> str:
        full_path = str(self.path)
        return full_path[:len(full_path) - len(self.path.suffix)]

    @cached_property
    def registry_key(self) -> str:
        target = self.path.stem.upper()
        parsed = re.match('(.+)_[0-9]{1,2}$', target)
        if parsed:
            target = parsed.groups()[0]
        return target

    @property
    def parent_folder(self) -> str:
        return self.path.parts[len(self.path.parts) - 2]

    def de_register(self):
        """
        Remove yourself from the the list of registered FileClean objects
        """
        if not self.is_registered():
            logger.error(f'Trying to remove non-existent {self.path}) from duplicate_hash')
        else:
            new_list = []
            key = self.path.name.upper()
            for value in self.duplicate_hash[key]:
                if not value == self:
                    new_list.append(value)
            if not new_list:
                del self.duplicate_hash[key]
            else:
                self.duplicate_hash[key] = new_list

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
        if self.registry_key in self.duplicate_hash:
            return self.duplicate_hash[self.registry_key]
        return []

    def register(self):
        if self.is_registered(by_path=True, by_file=True):
            logger.error(f'Trying to re_register {self.path})')
        else:
            key = self.registry_key
            if key not in self.duplicate_hash:
                self.duplicate_hash[key] = []
            self.duplicate_hash[key].append(self)

    @staticmethod
    def un_register(file_path: Path):

        entity = Cleaner(file_path)
        duplicate = entity.get_registered(by_path=True, by_file=False)
        if duplicate:
            duplicate.de_register()
        else:
            logger.error(f'Try to un_register {file_path}(not registered)')

    def get_registered(self, by_name: bool = True, by_path: bool = False, by_file: bool = False,
                       alternate_path: Path = None) \
            -> Optional[FileCT]:

        key = self.registry_key
        new_path = alternate_path if alternate_path else self.path.parent
        if key in self.duplicate_hash:
            for entry in self.duplicate_hash[key]:
                found_name = self.path.name.upper() == entry.path.name.upper() if by_name else True
                found_path = str(entry.path.parent) == str(new_path) if by_path else True

                if by_file:
                    logger.debug(f'Comparing {key} {entry.path} to {self.path}')
                    try:
                        found_file = self == entry
                    except FileNotFoundError:
                        found_file = False  # todo: This is for debugging - we should never have FileNotFound
                else:
                    found_file = True
                if found_name and found_path and found_file:
                    return entry
        return None

    def get_new_path(self, base: Path, invalid_parents: Optional[List] = []) -> Optional[Path]:
        """
        Using the time stamp and current location build a folder path to where this
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
        description = None
        if self.folder:
            description = self.folder.recursive_description_lookup('', invalid_parents)
            if not date:
                date = self.folder.date

        if not date and description:
            return Path(f'{base}{os.path.sep}{description}')
        if not date:
            return base

        year = month = day = None
        # Bug... all folders have a time.
        if self.date:
            year = self.date.year
            month = self.date.month
            day = self.date.day

        new = str(base)
        if year and description:
            new = f'{new}{os.path.sep}{year}{os.path.sep}{description}'
        elif year:
            new = f'{new}{os.path.sep}{year}'
            if month:
                new = f'{new}{os.path.sep}{month}'
                if day:
                    new = f'{new}{os.path.sep}{day}'
        if not os.path.exists(new):
            os.makedirs(new)
        return Path(new)

    def relocate_file(self,
                      path: Path,
                      remove: bool = False,
                      rollover: bool = True,
                      create_dir: bool = True,
                      register: bool = False):
        """
        :param path: A string representation of the folder
        :param remove: A boolean (default: False) Once successful on the relocate,   remove the original
        :param rollover: A boolean (default: True) rollover an existing file if it exists otherwise ignore
        :param create_dir: A boolean (default: True), create the directory if it does not exist,  if false and the
        :param register: A boolean (default:False), register this value after the move
        directory does not exist abort!
        :return:
        """

        if not path:
            return

        if not os.path.exists(path):
            if create_dir:
                os.makedirs(path)
            else:
                logger.debug(f'Create Dir is {create_dir},  not going to move {self.path.name} to {path}')
                return

        new = Path(f'{path}{os.path.sep}{self.path.name}')
        logger.debug(f'Copy {self.path} to {new}')
        if os.path.exists(new):
            if rollover:
                logger.debug(f'Rolling over {new}')
                self.rollover_name(new)
                copyfile(str(self.path), new)
            else:
                logger.debug(f'Will not overwrite {new}')
        else:
            copyfile(str(self.path), new)
        if remove:
            try:
                os.unlink(self.path)
            except OSError as e:
                logger.debug(f'{self.path} could not be removed ({e}')
        if register:
            self.path = new
            self.register()

    def get_date_from_path_name(self) -> Optional[datetime]:
        """
        Check the file name for an embedded time stamp
        :return: datetime or None
        """
        parser_values = [  # Used to loop over _get_date_from_path_name
            ['^([0-9]{8})-([0-9]{6})$', '%Y%m%d%H%M%S', 3],
            ['^([0-9]{8})_([0-9]{6})$', '%Y%m%d%H%M%S', 3],  # todo: clom these two up together using [-_] or .
            ['^([0-9]{4}).([0-9]{2}).([0-9]{2}).*', '%Y%m%d', 3],
            ['^([0-9]{2}).([a-zA-Z]{3}).([0-9]{4}).*', '%d%b%Y', 3],
            ['^([0-9]{4}).([0-9]{2}).+', '%Y%m', 2]
        ]

        def _get_date_from_path_name(name: str, regexp: str,  date_format: str, array_max: int) -> Optional[datetime]:
            re_parse = re.match(regexp, self.path.stem)
            if re_parse:
                re_array = re_parse.groups()
                date_string = "".join(re_array[0:array_max])
                try:
                    return datetime.strptime(date_string, date_format)
                except ValueError:
                    logger.debug(f'Could not convert {date_string} of {self.path.name} to a date')
            return None

        for exp, fmt, index in parser_values:
            value = _get_date_from_path_name(self.path.stem, exp, fmt, index)
            if value:
                return value
        return None

    def get_date_from_folder_names(self) -> Optional[datetime]:

        parse_tree = re.match('.*([0-9]{4}).([0-9]{1,2}).([0-9]{1,2})$', str(self.path))
        if parse_tree:
            try:
                return datetime(int(parse_tree.groups()[0]), int(parse_tree.groups()[1]), int(parse_tree.groups()[2]))
            except ValueError:
                pass

        parse_tree = re.match('.*([0-9]{4}).([0-9]{1,2})$', str(self.path))
        if parse_tree:
            try:
                return datetime(int(parse_tree.groups()[0]), int(parse_tree.groups()[1]), 1)
            except ValueError:
                pass

        parse_tree = re.match('^([0-9]{4})$', str(self.path.name))
        if parse_tree:
            try:
                return datetime(int(parse_tree.groups()[0]), 1, 1)
            except ValueError:
                pass

        parse_tree = re.match('^([0-9]{4})[A-Za-z].*', str(self.path.name))
        if parse_tree:
            try:
                return datetime(int(parse_tree.groups()[0]), 1, 1)
            except ValueError:
                pass
        return None

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

        if os.path.exists(destination):
            basename = destination.name[:len(destination.name) - len(destination.suffix)]
            for increment in reversed(range(20)):  # 19 -> 0
                old_path = f'{destination.parent}{os.path.sep}{basename}_{increment}{destination.suffix}'
                new_path = f'{destination.parent}{os.path.sep}{basename}_{increment + 1}{destination.suffix}'
                if os.path.exists(old_path):
                    if os.path.exists(new_path):
                        os.unlink(new_path)
                    os.rename(old_path, new_path)
            os.rename(destination, f'{destination.parent}{os.path.sep}{basename}_0{destination.suffix}')


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
        # With images,  an later time stamp is less of a file
        if self == other:
            if self.date and not other.date:
                return True
            if not self.date and other.date:
                return False
            if self.date and other.date:
                return self.date > other.date
        return False

    def __gt__(self, other):
        # With images,  a lesser timestamp is more of a file
        if self == other:
            if self.date and not other.date:
                return False
            if not self.date and other.date:
                return True
            if self.date and other.date:
                return self.date < other.date
        return False

    @property
    def requires_conversion(self):
        return self.path.suffix.upper() in self.files_to_convert

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

    @cached_property
    def date(self):
        if not self._date:
            self._date = self.get_date_from_image()
            if not self._date:  # Short circuit to find a date
                self._date = self.get_date_from_path_name() or self.get_date_from_folder_names() or self.folder.date
                if self._date:
                    self.update_image()
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
                except OSError:  # Invalid Image
                    logger.error(f'Warning - failed to read image: {self.path}')
                    self._image = None
        if opened:
            self.close_image()

    @property
    def image_data(self):
        self.load_image_data()
        return self._image_data

    def convert(self, migrated_base: Path, run_path: Path, keep: bool = True, in_place: bool = True) -> ImageCT:
        """
        :param run_path: Working directory to store temporary working files
        :param migrated_base:  Where (if any) to archive originals to
        :param in_place: default: True, if false ????
        :param keep:  default: True, and if so,  never try and update the input folder
        :return: self or a new object that's updated

        I think this also works with HEIC files
        """
        #  todo: Try this on HEIC files
        if self.path.suffix.upper() != '.HEIC':
            return self

        if platform.system() == 'Windows':
            logger.error('Conversion from HEIC is not supported on Windows')
            return self
        else:
            import pyheif

        if in_place:
            keep = False

        new_name = run_path.joinpath(f'{self.path.stem}.jpg')
        if new_name.exists():
            new_name.unlink()
            logger.debug(f'Cleaning up  {new_name} - It already exists')

        exif_dict = None
        heif_file = pyheif.read(self.path)
        image = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw", heif_file.mode,
                                heif_file.stride)
        try:
            for metadata in heif_file.metadata or []:
                if 'type' in metadata and metadata['type'] == 'Exif':
                    exif_dict = piexif.load(metadata['data'])

            if exif_dict:
                exif_bytes = piexif.dump(exif_dict)
                image.save(new_name, format("JPEG"), exif=exif_bytes)

                if migrated_base:
                    self.relocate_file(self.get_new_path(base=migrated_base), remove=not keep, rollover=False)
                return ImageCleaner(Path(new_name), self.folder)

        except AttributeError as e:
            logger.error(f'Conversion error: {self.path} - Reason {e} is no metadata attribute')
        return self

    def update_image(self):
        """
        Update an image file with the data provided
        :return: None
        """
        changed = False
        try:
            exif_dict = piexif.load(str(self.path))
            logger.debug(f'Update Image - success loading {self.path}')
            if self._date:
                new_date = self._date.strftime("%Y:%m:%d %H:%M:%S")
                exif_dict['0th'][piexif.ImageIFD.DateTime] = new_date
                exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = new_date
                exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = new_date
                changed = True
            if changed:
                try:
                    exif_bytes = piexif.dump(exif_dict)
                    piexif.insert(exif_bytes, str(self.path))
                except ValueError as e:
                    logger.error(f'Failed to update {self.path} Error {e}')

        except piexif.InvalidImageDataError:
            logger.debug(f'Failed to load {self.path} - Invalid JPEG/TIFF')
        except FileNotFoundError:
            logger.error(f'Failed to load {self.path} - File not Found')

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
                except ValueError:
                    logger.debug(f'Corrupt date data {self.path}')
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
    no_date_folder is Path of the folder for files with no dates (value is cached)
    parent,  the FolderCleaner object we are from.

    """

    cached_root_folder = None
    cached_output_folder = None
    cached_no_date_folder = None

    def __init__(self, path_entry: Path,
                 root_folder: Path = None,
                 output_folder: Path = None,
                 no_date_folder: Path = None,
                 parent: FolderCT = None):

        super().__init__(path_entry, parent)

        if not self.cached_root_folder and root_folder:
            self.cached_root_folder = root_folder

        if not self.cached_output_folder and output_folder:
            self.cached_output_folder = output_folder

        if not self.cached_no_date_folder and no_date_folder:
            self.cached_no_date_folder = no_date_folder

        self.root_folder: Path = root_folder if root_folder else self.cached_root_folder
        self.no_date_folder: Path = no_date_folder if no_date_folder else self.cached_no_date_folder
        self.output_folder: Path = output_folder if output_folder else self.cached_output_folder

        self.description: Optional[str] = self.get_description_from_path()
        self.parent: Optional[FolderCT] = parent

    def __eq__(self, other):
        # Comparison is based first on custom folder (vs just arbitrary dates)
        if self.custom_folder and other.custom_folder or (not self.custom_folder and not other.custom_folder):
            return True
        return False

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        if not self == other:
            if not self.custom_folder:
                return True
        return False

    def __gt__(self, other):
        if not self == other:
            if self.custom_folder:
                return True
        return False

    @property
    def size(self):
        count = 0
        for item in self.path.iterdir():
            count += 1
        return count

    @property
    def is_small(self):
        """
        artibraty small is 10
        :return:
        """
        return self.size < 10

    def _get_description_from_path_name(self, regexp: str, array_max: int) -> Optional[str]:
        re_parse = re.match(regexp, self.path.name)
        if re_parse:
            re_array = re_parse.groups()
            return re_array[array_max].rstrip().lstrip()
        return None

    @cached_property
    def custom_folder(self) -> bool:
        """
        A utility to test if the folder was explicitly named (thus custom)

        A custom folder is a folder that does not end with a date format YYYY/MM/DD but has the date format in it
        :return: boolean  - True if a custom folder

        .../2012/3/3/foobar is custom
        .../foo/bar is NOT custom
        .../2012/3/3 is NOT managed
        """

        folder = str(self.path)
        if not re.match('.*[0-9]{4}.[0-9]{1,2}.[0-9]{1,2}$', folder):
            if not folder == str(self.output_folder):
                if not folder == str(self.root_folder):
                    if not folder.startswith(str(self.no_date_folder)):
                        return True
        return False

    @cached_property
    def date(self) -> Optional[datetime]:
        if not self._date:
            if not (len(self.path.name) == 22 and self.path.name.find(' ') == -1):  # Get rid of garbage first
                self._date = self.get_date_from_path_name() or self.get_date_from_folder_names()   # short circuit

        if not self._date:
            # Use the parent date
            folder = self.folder
            while folder:
                if folder.date:
                    self._date = folder.date
                    break
                folder = folder.folder
        return self._date

    def get_description_from_path(self) -> Optional[str]:
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
        return description

    def recursive_description_lookup(self, current_description: str, to_exclude) -> str:
        """
        Recurse your parents to build up path based on descriptive folder names
        :param current_description:  a string with the build up path
        :param to_exclude: an array of path components that we don't want to include in description tree

        :return: a string with the path name based on os.path.sep and the various folder levels
        """
        if self.description:
            if self.description not in to_exclude:
                current_description = f'{os.path.sep}{self.description}{current_description}'
            if self.parent:
                current_description = self.parent.recursive_description_lookup(current_description, to_exclude)
        return current_description

    def reset(self):
        self.cached_root_folder = None
        self.cached_no_date_folder = None
        self.cached_output_folder = None


class ImageClean:

    def __init__(self, app: str, restore=False, **kwargs):
        self.app_name = app
        self.run_path = Path(Path.home().joinpath(f'.{self.app_name}'))
        if not self.run_path.exists():
            os.makedirs(self.run_path, mode=511, exist_ok=True)
        self.conf_file = self.run_path.joinpath('config.pickle')

        # Default option/values
        self.input_folder = Path.home()
        self.output_folder = Path.home()
        self.verbose = True
        self.do_convert = True  # todo: Provide an option for this
        self.recreate = False
        self.force_keep = False  # With R/O directories we can not ever try and remove anything
        self.keep_duplicates = False
        self.keep_movie_clips = False
        self.process_all_files = False  # todo: re-evaluate this
        self.keep_converted_files = False
        self.keep_original_files = True
        self.do_not_process = []
        self.ignore_folders = []
        self.bad_parents = []
        self.progress = 0

        if restore:  # Used by UI
            try:
                f = open(self.conf_file, 'rb')
                temp = pickle.load(f)
                self.process_args(temp)
            except FileNotFoundError:
                pass
        else:  # Used by cmdline
            self.process_args(kwargs)

        self.duplicate_path_base = f'{self.app_name}_Duplicates'
        self.movie_path_base = f'{self.app_name}_ImageMovies'
        self.converted_path_base = f'{self.app_name}_Migrated'
        self.no_date_base = f'{self.app_name}_NoDate'
        self.small_base = f'{self.app_name}_Small'

        self.in_place = False
        self.no_date_path = None
        self.small_path = None
        self.migrated_path = None
        self.duplicate_path = None
        self.image_movies_path = None

    def process_args(self, kwargs: dict):
        for key in kwargs:
            if key == 'verbose':
                self.verbose = kwargs[key]
            elif key == 'recreate':
                self.recreate = kwargs[key]
            elif key == 'do_convert':
                self.do_convert = kwargs[key]
            elif key == 'input':
                self.input_folder = kwargs[key]
            elif key == 'output':
                self.output_folder = kwargs[key]
            elif key == 'keep_duplicates':
                self.keep_duplicates = kwargs[key]
            elif key == 'keep_clips':
                self.keep_movie_clips = kwargs[key]
            elif key == 'keep_conversions':
                self.keep_converted_files = kwargs[key]
            elif key == 'keep_originals':
                self.keep_original_files = kwargs[key]
            elif key == 'ignore_folders':
                for value in kwargs[key]:
                    self.ignore_folders.append(value)
            elif key == 'bad_parents':
                for value in kwargs[key]:
                    self.bad_parents.append(value)
            else:
                assert False, f'Invalid option supplied: {key}'

    def save_config(self):
        config = {'verbose': self.verbose,
                  'recreate': self.recreate,
                  'do_convert': self.do_convert,
                  'input': self.input_folder,
                  'output': self.output_folder,
                  'keep_duplicates': self.keep_duplicates,
                  'keep_clips': self.keep_movie_clips,
                  'keep_conversions': self.keep_converted_files,
                  'keep_originals': self.keep_original_files,
                  'ignore_folders': self.ignore_folders,
                  'bad_parents': self.bad_parents,
                  }
        with open(self.conf_file, 'wb') as f:
            pickle.dump(config, f, pickle.HIGHEST_PROTOCOL)

    def print(self, text):
        if self.verbose:
            print(text)

    def increment_progress(self):
        self.progress += 1

    def set_recreate(self, value: bool):
        self.recreate = value

    def set_keep_duplicates(self, value: bool):
        self.keep_duplicates = value

    def set_keep_movie_clips(self, value: bool):
        self.keep_movie_clips = value

    def set_keep_converted_files(self, value: bool):
        self.keep_converted_files = value

    def set_keep_original_files(self, value: bool):
        self.keep_original_files = value

    def add_ignore_folder(self, value: Path):
        if value not in self.ignore_folders:
            self.ignore_folders.append(value)
            return True
        return False

    def add_bad_parents(self, value: Path):
        if value not in self.bad_parents:
            self.bad_parents.append(value)
            return True
        return False

    def set_paranoid(self, value: bool):
        self.set_keep_duplicates(value)
        self.set_keep_original_files(value)
        self.set_keep_converted_files(value)
        self.set_keep_movie_clips(value)
        self.force_keep = value

    def prepare(self):
        """
        Some further processing once all the options have been set.
        """

        assert os.access(self.output_folder, os.W_OK | os.X_OK)
        self.force_keep = os.access(self.input_folder, os.W_OK | os.X_OK) | self.force_keep  # in case we are paranoid

        if self.output_folder == self.input_folder:
            if self.recreate:
                assert False, f'Can not recreate with same input/output folders: {self.input_folder}\n\n'
            self.in_place = True
            self.force_keep = False  # This just makes no sense - even IF paranoid, the point is to move files !

        # Make sure we ignore these,  they came from us.
        self.ignore_folders.append(self.output_folder.joinpath(self.movie_path_base))
        self.ignore_folders.append(self.output_folder.joinpath(self.duplicate_path_base))
        self.ignore_folders.append(self.output_folder.joinpath(self.converted_path_base))
        self.ignore_folders.append(self.output_folder.joinpath(self.small_base))

        self.bad_parents.append(self.no_date_base)
        self.bad_parents.append(self.movie_path_base)
        self.bad_parents.append(self.duplicate_path_base)
        self.bad_parents.append(self.converted_path_base)
        self.bad_parents.append(self.small_base)

        self.no_date_path = self.output_folder.joinpath(self.no_date_base)
        self.small_path = self.output_folder.joinpath(self.small_base)

        if self.keep_converted_files:
            self.migrated_path = self.output_folder.joinpath(self.converted_path_base)

        if self.keep_duplicates:
            self.duplicate_path = self.output_folder.joinpath(self.duplicate_path_base)

        if self.keep_movie_clips:
            self.image_movies_path = self.output_folder.joinpath(self.movie_path_base)

        # Backup any previous attempts

        if not self.recreate or self.in_place:  # Same root or importing from a new location
            self.register_files(self.output_folder)

        if self.recreate:
            if self.output_folder.exists():
                os.rename(self.output_folder, f'{self.output_folder}_{datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}')

        os.mkdir(self.output_folder) if not self.output_folder.exists() else None
        os.mkdir(self.no_date_path) if not self.no_date_path.exists() else None
        os.mkdir(self.migrated_path) if self.migrated_path and not self.migrated_path.exists() else None
        os.mkdir(self.duplicate_path) if self.duplicate_path and not self.duplicate_path.exists() else None
        os.mkdir(self.image_movies_path) if self.image_movies_path and not self.image_movies_path.exists() else None
        os.mkdir(self.small_path) if self.small_path and not self.small_path.exists() else None

    def register_files(self, output_dir: Path):
        """
        Take an inventory of all the existing files.    This allows us to easily detected duplicate files.
        :param output_dir:  where we will be moving file to
        :return:
        """
        for entry in output_dir.iterdir():
            if entry.is_dir():
                self.register_files(entry)
            else:
                #if not entry.parent == output_dir:  # The base of the output directory should not contain files,  if
                                                    # it does they were not added by us so they need to be pr
                file_cleaner(entry, FolderCleaner(output_dir)).register()

    @staticmethod
    def duplicate_get(entry: Union[ImageCleaner, FileCleaner]) -> Optional[Union[ImageCleaner, FileCleaner]]:
        matched = None
        for value in entry.get_all_registered():
            if entry == value:
                if entry.path == value.path:  # The image data is exactly the same
                    return value
                else:
                    matched = value
        logger.error(f'Expecting to find a duplicate for {entry.path}')
        return matched

    @staticmethod
    def duplicates_test(entry: Union[ImageCleaner, FileCleaner]) -> int:
        """
        Test for duplicates, based on registered files
        :param entry: The instance of the current file
        :return: int,
        """

        result = NEW_FILE
        if entry.is_small:
            result = SMALL_FILE
        elif not entry.is_registered():
            result = NEW_FILE  # This is a new FileCleaner instance.
        else:
            for value in entry.get_all_registered():
                if entry == value:  # The data is exactly the same
                    if entry.folder == value.folder:  # Folders have same weight
                        if entry < value:
                            return LESSER_FILE
                        elif entry > value:
                            return GREATER_FILE
                    elif entry.folder > value.folder:
                        return GREATER_FILE
                    elif entry.folder < value.folder:
                        return LESSER_FILE

                    # Lets use the file date
                    if entry.date == value.date:
                        if entry.folder.date == value.folder.date:
                            return EXACT_FILE
                        elif entry.folder.date and value.folder.date:
                            if entry.folder.date < value.folder.date:
                                return GREATER_FILE
                            elif entry.folder.date > value.folder.date:
                                return LESSER_FILE
                        if entry.folder.date and not value.folder.date:
                            return GREATER_FILE
                        if not entry.folder.date and value.folder.date:
                            return LESSER_FILE
                    elif entry.date < value.date:
                        return GREATER_FILE
                    else:
                        return LESSER_FILE
                    return EXACT_FILE
        return result

    def process_duplicates_movies(self, movie_dir):
        for entry in movie_dir.path.iterdir():
            if entry.is_dir():
                self.process_duplicates_movies(FolderCleaner(Path(entry), movie_dir.root_folder, parent=movie_dir))
            elif entry.is_file():
                file_entry = FileCleaner(Path(entry), folder=movie_dir)
                if file_entry.path.suffix in file_entry.all_movies:
                    # todo: Use .stem property ...
                    just_name = file_entry.just_name
                    for suffix in file_entry.all_images:
                        if FileCleaner(Path(f'{just_name}{suffix}')).is_registered():
                            if self.image_movies_path:
                                self.print(f'.... Saving Clip {file_entry.path}')
                                file_entry.relocate_file(self.image_movies_path, remove=True)
                            else:
                                self.print(f'.... Removing Clip {file_entry.path}')
                                os.unlink(file_entry.path)
                            break

    def audit_folders(self, path: Path) -> List[Path]:
        large_folders = []
        for entry in path.iterdir():
            if entry.is_dir():
                self.audit_folders(entry)
                size = len(os.listdir(entry))
                if size == 0:
                    self.print(f'  Removing empty folder {entry}')
                    os.rmdir(entry)
                elif size > WARNING_FOLDER_SIZE:
                    large_folders.append(entry)
                    self.print(f'  VERY large folder ({size}) found {entry}')
        return large_folders

    def process_file(self, entry: Union[FileCleaner, ImageCleaner]):
        """
        Perform any conversions
        Extract image date
        Calculate new destination folder
        Test Duplicate status

        :param entry: Cleaner object,  promoted to a subclass when processed
        """
        self.print(f'.. File: {entry.path}')
        self.increment_progress()

        if not entry.is_valid:
            self.print(f'.... File {entry.path} is invalid.')
            return

        new_entry = entry.convert(self.migrated_path, self.run_path, in_place=self.in_place, keep=self.force_keep)
        if id(new_entry) != id(entry):  # The file was converted and cleaned up
            entry = new_entry  # work on the converted file

        if not self.process_all_files:
            if entry.path.suffix not in entry.all_images:
                if entry.path.suffix not in entry.all_movies:
                    self.print(f'.... Ignoring non image file {entry.path}')
                    return

        # Now lets go about building our output folder
        if entry.date:
            new_path = entry.get_new_path(self.output_folder, invalid_parents=self.bad_parents)
        else:  # make sure we do not over process things already determined to not be 'no date' files.
            if str(entry.path.parent).startswith(str(self.no_date_path)):
                new_path = entry.path.parent
            else:
                new_path = entry.get_new_path(self.no_date_path)

        dup_result = self.duplicates_test(entry)
        logger.debug(f'Duplicate Test: {dup_result} - {entry.path}')
        if dup_result == NEW_FILE:  # We have not seen this file before
            entry.relocate_file(new_path, register=True,  rollover=True,
                                remove=not self.keep_original_files or self.in_place or not self.force_keep)
        elif dup_result == SMALL_FILE:  # This file was built by some post processor (apple/windows) importer
            entry.relocate_file(entry.get_new_path(self.small_path), rollover=False,
                                remove=not self.keep_original_files or not self.force_keep)
        elif dup_result in (GREATER_FILE, LESSER_FILE, EXACT_FILE):
            existing = self.duplicate_get(entry)
            if not entry.path == existing.path:  # We are the same file,  do nothing
                if dup_result in (LESSER_FILE, EXACT_FILE):
                    entry.relocate_file(entry.get_new_path(self.duplicate_path), create_dir=False, rollover=False,
                                        remove=not self.keep_original_files or self.in_place or not self.force_keep)
                elif dup_result == GREATER_FILE:
                    existing.relocate_file(existing.get_new_path(self.duplicate_path),
                                           remove=not self.keep_original_files or not self.force_keep,
                                           create_dir=False, rollover=False)
                    entry.relocate_file(new_path, register=True, remove=self.in_place or not self.force_keep,
                                        rollover=False)
        else:
            assert False, f'Invalid test result {dup_result}'

    def process_folder(self, folder: FolderCleaner):
        self.print(f'. Folder: {folder.path}')
        for entry in folder.path.iterdir():
            if entry.is_dir() and entry not in self.ignore_folders:
                this_folder = FolderCleaner(Path(entry), parent=folder)
                if this_folder.description in self.bad_parents:
                    this_folder.description = None
                self.process_folder(this_folder)
            elif entry.is_file():
                self.process_file(file_cleaner(entry, folder))
            else:
                self.print(f'. Folder: {entry} ignored ')
        folder.clean_working_dir(self.run_path)  # Cleans up any temporary files that have been made
