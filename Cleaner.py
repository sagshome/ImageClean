import imghdr
import logging
import os
import re

import piexif
import pyheif

from datetime import datetime
from filecmp import cmp
from functools import cached_property
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from shutil import copyfile
from typing import List, Dict, Optional, TypeVar, Union

logger = logging.getLogger('image_clean')


IMAGE_FILES = ['.JPG', '.HEIC', '.AVI', '.MP4', '.THM', '.RTF', '.PNG', '.JPEG', '.MOV', '.TIFF']
SMALL_IMAGE = 360  # If width and height are less then this, it is thumb nail or some other derived file.

CT = TypeVar("CT", bound="Cleaner")
FileCT = TypeVar("FileCT", bound="FileCleaner")
ImageCT = TypeVar("ImageCT", bound="ImageCleaner")
FolderCT = TypeVar("FolderCT", bound="FolderCleaner")


def file_cleaner(file: Path, folder: Optional[FolderCT]) -> Union[FileCT, ImageCT, FolderCT]:
    logger.debug(f'Go for it:{file}')
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

    def convert(self, migrated_path: Path = None, remove: bool = True) -> CleanerCT:
        return self  # If required and successful return new Cleaner object / vs self

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
        return self.path.name[:len(self.path.name) - len(self.path.suffix)]

    @property
    def just_path(self) -> str:
        full_path = str(self.path)
        return full_path[:len(full_path) - len(self.path.suffix)]

    @cached_property
    def registry_key(self) -> str:
        target = self.just_name.upper()
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

    def get_registered(self, by_name: bool = True, by_path: bool = False, by_file: bool = False, alternate_path: Path = None) \
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
        self._make_new_path(Path(new))
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
                self._make_new_path(path)
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
            os.unlink(self.path)
        if register:
            self.register()

    def get_date_from_path_name(self) -> Optional[datetime]:
        """
        Check the file name for an embedded time stamp
        :return: datetime or None
        """
        parser_values = [  # Used to loop over _get_date_from_path_name
            ['^([0-9]{8})-([0-9]{6})$', '%Y%m%d%H%M%S', 3],
            ['^([0-9]{4}).([0-9]{2}).([0-9]{2}).*', '%Y%m%d', 3],
            ['^([0-9]{2}).([a-zA-Z]{3}).([0-9]{4}).*', '%d%b%Y', 3],
            ['^([0-9]{4}).([0-9]{2}).+', '%Y%m', 2]
        ]

        def _get_date_from_path_name(name: str, regexp: str,  date_format: str, array_max: int) -> Optional[datetime]:
            re_parse = re.match(regexp, self.path.name)
            if re_parse:
                re_array = re_parse.groups()
                date_string = "".join(re_array[0:array_max])
                try:
                    return datetime.strptime(date_string, date_format)
                except ValueError:
                    logger.debug(f'Could not convert {date_string} of {self.path.name} to a date')
            return None

        for exp, fmt, index in parser_values:
            value = _get_date_from_path_name(self.path.name, exp, fmt, index)
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

    @staticmethod
    def _make_new_path(path: Path):
        parts = path.parts
        folder = None
        for part in parts[0:len(parts)]:
            folder = f'{folder}{os.path.sep}{part}' if not part == os.path.sep else os.path.sep
            if not os.path.exists(folder):
                os.mkdir(folder)


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
                logger.debug(f'{self.path} - {e.strerror}')
            except OSError as e:
                logger.debug(f'{self.path} - {e.strerror}')
        return self._image

    def load_image_data(self):
        opened = False
        if not self._image_data:
            if not self._image:
                self.open_image()
                opened = True
            if self._image:
                for val in self._image.getdata().split():
                    self._image_data.append(val.histogram())
        if opened:
            self.close_image()

    @property
    def image_data(self):
        self.load_image_data()
        return self._image_data

    def convert(self, migrated_path: Path = None, remove: bool = True) -> ImageCT:
        """
        :param migrated_path:  Where (if any) to archive originals to
        :param remove:  default: True - Cleanup after successful conversion
        :return: self or a new object thats updated

        I think this also works with HEIC files
        """

        if self.path.suffix.upper() != '.HEIC':
            return self

        new_name = f'{self.just_path}.jpg'
        if os.path.exists(new_name):
            logger.debug(f'Will not convert {self.path} to {new_name} - It already exists')
        else:
            heif_file = pyheif.read(self.path)
            image = Image.frombytes(heif_file.mode,
                                    heif_file.size,
                                    heif_file.data,
                                    "raw",
                                    heif_file.mode,
                                    heif_file.stride,
                                    )
            exif_dict = None
            try:
                for metadata in heif_file.metadata or []:
                    if metadata['type'] == 'Exif':
                        exif_dict = piexif.load(metadata['data'])

                if exif_dict:
                    exif_bytes = piexif.dump(exif_dict)
                    image.save(new_name, format("JPEG"), exif=exif_bytes)

                    if migrated_path:
                        self.relocate_file(migrated_path, remove=True, rollover=False)
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
                exif_bytes = piexif.dump(exif_dict)
                piexif.insert(exif_bytes, str(self.path))

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
