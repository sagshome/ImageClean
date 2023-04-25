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

logger = logging.getLogger('Cleaner')


IMAGE_FILES = ['.JPG', '.HEIC', '.AVI', '.MP4', '.THM', '.RTF', '.PNG', '.JPEG', '.MOV', '.TIFF']
SMALL_IMAGE = 360  # If width and height are less than this, it is thumbnail or some other derived file.
SMALL_FOLDER = 30  # Less than this and we should consider the folder small.

CT = TypeVar("CT", bound="Cleaner")  # pylint: disable=invalid-name
FileCT = TypeVar("FileCT", bound="FileCleaner")  # pylint: disable=invalid-name
ImageCT = TypeVar("ImageCT", bound="ImageCleaner")  # pylint: disable=invalid-name
FolderCT = TypeVar("FolderCT", bound="Folder")  # pylint: disable=invalid-name

# A couple of caches
output_files: Dict[str, List[CT]] = {}  # This is used to store output files  - each element is a file clearner
output_folders: Dict[str, FolderCT] = {}  # This is used to store output folders

# Inter-instance data
PICTURE_FILES = ['.jpg', '.jpeg', '.tiff', '.tif', '.png', '.bmp', '.heic']
MOVIE_FILES = ['.mov', '.avi', '.mp4']


def make_cleaner_object(entry: Path) -> Union[FileCT, ImageCT, FolderCT]:
    """
    shortcut for making Cleaner Objects,   if it is a folder,  check for a cached copy first.
    :param: entry  - A path object representing the folder or the file
    :return:
    """
    assert not entry.is_dir()
    # entry must be a file
    suffix = entry.suffix.lower()
    if suffix in PICTURE_FILES or suffix in MOVIE_FILES:
        return ImageCleaner(entry)
    return FileCleaner(entry)
# Compile once for performance


FOLDER_PARSERS = [  # Used to loop over _get_date_from_path_name
    [re.compile(r'(.*)([1-2]\d{3})[\\/\-_ ](\d{1,2})[\\/\-_ ](\d{1,2})(.*)'), '%Y%m%d', 3, 'Day'],  # ...1961/09/27
    [re.compile(r'(.*)(\d{2})[\\/\-_ ]([a-zA-Z]{3})[\\/\-_ ]([1-2]\d{3})(.*)'), '%d%b%Y', 3, 'Day'],  # ...27-Sep-1961
    [re.compile(r'(.*)([1-2]\d{3})[\\/\-_ ](\d{1,2})(.*)'), '%Y%m', 2, 'Month'],  # ...1961/09
    [re.compile(r'(.*)(\d{8})[_-]\d{6}(.*)'), '%Y%m%d', 1, 'Day'],  # ...19610927-010203
    [re.compile(r'(.*)([1-2]\d{3})(.*)'), '%Y', 1, 'Year'],  # ...1961
    [re.compile(r'(.*)'), None, 0, '']  # Whatever we have must be the description (if any)
]

FN_DATE = re.compile(r'^([1-2]\d{3})([0-1]\d)([0-3]\d)_\d{6}')
YEAR = re.compile(r'^[1-2]\d{3}$')
MONTH_OR_DAY = re.compile(r'^\d{2}$')
CLEAN = re.compile(r'^[ \-_]+')
SKIP_FOLDER = re.compile(r'^\d{8}-\d{6}$')


class CleanerBase:
    """
    A class to encapsulate the Path object that is going to be cleaned
    """
    def __init__(self, path_entry: Path):
        self.path = path_entry
        self._date = None
        self._metadate = False  # Is set when retrieving the date.

    def __eq__(self, other) -> bool:
        if self.__class__ == other.__class__:
            try:
                if os.stat(self.path).st_size == os.stat(other.path).st_size:
                    return cmp(self.path, other.path, shallow=False)
            except FileNotFoundError:
                logger.error('File %s or %s does not exists', self.path, other.path)
        return False

    def __lt__(self, other) -> bool:
        raise NotImplementedError

    def __gt__(self, other) -> bool:
        raise NotImplementedError

    def __ne__(self, other) -> bool:
        return not self == other

    def registered(self, entry: Path) -> bool:
        """
        Test if a file has been registered.   Understand the impacts of rolled over so FOO_0 and FOO are the same
        :param entry:
        :return:
        """
        assert self.is_file

        target = entry.stem.upper()
        parsed = re.match('(.+)_[0-9]{1,2}$', target)
        if parsed:
            target = parsed.groups()[0]
        return target in output_files

    @cached_property
    #@property
    def is_file(self):
        """
        cached value to see if a path is a file or not.
        :return:
        """
        return self.path.is_file()

    @property
    def metadate(self) -> bool:
        """
        getter for determining is we got the data from the image itself or some other source.
        :return: Boolean
        """
        return self._metadate

    def convert(self, work_dir: Path, migrated_base: Optional[Path], remove: bool = True) -> FileCT:  # pylint: disable=unused-argument
        """
        Stub for converting,  only one type now but who knows
        :param work_dir:
        :param migrated_base:
        :param remove:
        :return:
        """
        return self  # If required and successful return new Cleaner subclass object / vs self

    @property
    def date(self) -> Optional[datetime]:
        """
        the date of an object
        :return:
        """
        return self._date

    @property
    def folder(self) -> Optional[FolderCT]:
        key = self.path.parent.as_posix()
        if key in output_folders:
            return output_folders[key]
        return None

    def set_date(self):
        """
        How dates are set is based (and implemented) at the sub-class level
        By default set the atime, mtime based on stored time
        :return:
        """
        if self.path.exists() and self.date:
            os.utime(self.path, (self.date.timestamp(), self.date.timestamp()))

    @property
    def is_small(self) -> bool:
        """
        A test for garbage files
        :return:
        """
        raise NotImplementedError

    @property
    def is_valid(self) -> bool:
        """
        A way to define and enhance a good file
        :return:
        """
        raise NotImplementedError

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

    def register(self):
        """
        Register the existence of a file and update the folder count.
        :return:
        """

        if self.registry_key not in output_files:
            output_files[self.registry_key] = []
        output_files[self.registry_key].append(self)

        if self.folder:
            self.folder.count += 1

    def de_register(self, silent=False):
        """
        Remove yourself from the list of registered FileClean objects
        """
        if not self.is_registered():
            if not silent:
                logger.error('Trying to remove non-existent %s from output files hashing', self.path)
        else:
            new_list = []
            for value in output_files[self.registry_key]:
                if not value == self:
                    new_list.append(value)
            if not new_list:
                del output_files[self.registry_key]
            else:
                output_files[self.registry_key] = new_list

    def is_registered(self, by_path: bool = False, new_path: Path = None) -> bool:
        """
        Test for existing of a file
        :param by_path:   Ensure a match on the existing path
        :param new_path:  Ensure a match on this other path
        :return:  True if exists
        """
        return self.get_registered(by_path, new_path) is not None

    def get_registered(self, by_path: bool = False, new_path: Path = None) -> Optional[CT]:
        """
        Retrieve an existing file object
        :param by_path:   Ensure a match on the existing path
        :param new_path:  Ensure a match on this other path
        :return:  object or None
        """
        by_path = True if new_path else by_path

        if self.registry_key in output_files:
            if not by_path:
                return output_files[self.registry_key][0]

            path_to_test = new_path if new_path else self.path
            for value in output_files[self.registry_key]:
                if value.path == path_to_test:
                    return value

        return None

    # File manipulation

    def test_for_duplicate(self, other):
        """
        Compare a file to the registered versions and return True if exactly equal to one
        :return:
        """
        if self.registry_key in output_files:
            for entry in output_files[self.registry_key]:
                if entry == other:
                    return True
        return False

    def build_base(self) -> Path:
        """
        Based on date values,   build a set of directories on YYYY/MM/DD
        :return:
        """
        result = Path()
        if self.date:
            result = Path(str(self.date.year)).joinpath(str(self.date.month)).joinpath(str(self.date.day))
        return result

    def add_date_to_path(self, base_path: Path) -> Path:
        """
        Process the file path to glean the descriptive path parts
        Anything,  that is not garbage or not a number/date is removed and the path portion is returned

        :param base_path:
        :return:
        """
        if base_path == Path():  # No existing path bases,  so just use the date.
            if self.date:
                base_path = Path(str(self.date.year)).joinpath(str(self.date.month)).joinpath(str(self.date.day))
                if not base_path.exists():
                    base_path = Path(str(self.date.year)).joinpath(str(self.date.month))
                    if not base_path.exists():
                        base_path = Path(str(self.date.year))
        else:  # We already have a path description,  so just use the year.
            base_path = Path(str(self.date.year)).joinpath(base_path)
        return base_path

    def relocate_file(self, new_path: Path, remove: bool = False, rollover: bool = True, register: bool = False):
        """
        :param new_path: A string representation of the folder
        :param remove: A boolean (default: False) Once successful on the relocate,   remove the original
        :param rollover: A boolean (default: True) rollover an existing file if it exists otherwise ignore
        :param register: A boolean (default:False), register this value after the move
        directory does not exist abort!
        :return:
        """
        new_file = None
        copied = False
        if new_path:
            if not new_path.exists():
                os.makedirs(new_path)
            new_file = new_path.joinpath(self.path.name)
            if self.path == new_file:  # pragma: no cover
                logger.debug('Will not copy to myself %s', new_file)
                return
            if new_file.exists():
                if rollover:
                    logger.debug('Rolling over %s', new_file)
                    self.rollover_file(new_file)
                else:
                    logger.debug('Will not overwrite %s', new_file)
                    remove = False

            if not new_file.exists():
                try:
                    copyfile(str(self.path), new_file)
                    copied = True
                except PermissionError as error:
                    logger.error('Can not write to %s - %s', new_path, error)

        if remove and copied:
            try:
                self.de_register(silent=True)
                os.unlink(self.path)
            except OSError as error:   # pragma: escape_win
                logger.debug('%s could not be removed (%s)', self.path, error)

        if copied:
            self.path = new_file
            self.set_date()

        if register and new_file and copied:
            self.register()

    @staticmethod
    def rollover_file(destination: Path):
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
                if old_path.exists():
                    new_path = destination.parent.joinpath(f'{destination.stem}_{increment + 1}{destination.suffix}')
                    if new_path.exists():
                        os.unlink(new_path)
                    os.rename(old_path, new_path)
            os.rename(destination, destination.parent.joinpath(f'{destination.stem}_0{destination.suffix}'))

    @classmethod
    def clear_caches(cls):
        """
        Get rid of all that cheesy persistent class data
        :return:
        """
        output_files.clear()
        output_folders.clear()


class Folder(CleanerBase):
    """
    Structure to calculate folder data,  date values description parts
        Process the file path to glean the descriptive path parts including dates
        Result should be:          Input Examples:  (other than existing results)
        YYYY/Text/ or              YYYY-MM-Text
        YYYY/MM/ or                Text
        YYYY/MM/Text/              YYYY/MM/DD/YYYYMMDD-HHMMSS/22_char_garbage/
        YYYY/MM/DD/                YYYY Text
        YYYY/MM/DD/Text/           YYYY-MM-DD-Text

        Anything,  that is not garbage or not a number/date is removed and the path portion is returned
    """

    def __init__(self, path_entry: Path, base_entry: Path = None, internal: bool = False, cache: bool = True):
        super().__init__(path_entry)

        self.dates: Dict = {
            'date': None,  # the time stamp (if any)
            'date_leaf': False,  # on a multi-part dated
            'month': False,  # set to True if the date really contained a month (by default month is 1)
            'day': False,  # set to True if the date really contained a day (by default day is 1)
        }
        self.description: str = None
        self.internal = internal  # Bool to indicate this is an internal folder so no need to process it
        self.count: int = 0  # How many files in this folder
        self.children: List[FolderCT] = []  # Maybe a django reverse lookup would be better.

        significant_path = self._significant_path(base_entry)

        if YEAR.match(str(path_entry.stem)) or MONTH_OR_DAY.match(str(path_entry.stem)):
            self.dates['date_leaf'] = True

        self.set_date_and_description(significant_path)

        key = self.path.as_posix()
        if cache and key not in output_folders:
            output_folders[key] = self

    def __lt__(self, other) -> bool:
        pass

    def __gt__(self, other) -> bool:
        pass

    @property
    def is_small(self) -> bool:
        pass

    @property
    def is_valid(self) -> bool:
        pass

    @classmethod
    def is_internal(cls, path: Path) -> bool:
        """
        Check the cache to see if a FolderData instance exists and if it is an internal folder
        :param path:
        :return:
        """
        path_str = str(path)
        if path_str in output_folders and output_folders[path_str].internal:
            return True
        return False

    @classmethod
    def get_folder(cls, path: Path) -> Union[FolderCT, None]:
        """
        Parse the cache and return a FolderData instance (if it exists)
        :param path:
        :return:
        """
        path_str = path.as_posix()
        if path_str in output_folders:
            return output_folders[path_str]
        return None

    @property
    def date(self) -> Optional[datetime]:
        return self.dates['date']

    @property
    def total(self) -> int:
        """
        recursive call to get all file counts
        :return: value of all folders/sub-folders added
        """
        count = self.count
        for child in self.children:
            count = count + child.total
        return count

    def build_base(self) -> Path:
        """
        Based on date values,   build a set of directories on YYYY/MM/DD
        :return:
        """
        result = Path()
        if self.date:
            result = Path(str(self.folder.date.year))
            if self.folder.dates['month']:
                result = result.joinpath(str(self.folder.date.month))
                if self.folder.dates['day']:
                    result = result.joinpath(str(self.folder.date.day))
        return result

    def _significant_path(self, base: Path = None):
        try:
            significant_path = self.path if not base else self.path.relative_to(base)
        except ValueError:
            significant_path = self.path

        return significant_path

    def _set_path_description(self, path_string):
        result = Path()
        path = Path(path_string)
        for part in path.parts:
            if part != '.' and not (len(part) == 22 and part.find(' ') == -1):
                try:
                    int(part)
                except ValueError:
                    if not SKIP_FOLDER.match(part):  # Date folder looking like a string
                        result = result.joinpath(CLEAN.sub('', part.rstrip()))

        if result.root:
            first = True
            new = Path()
            for part in result.parts:
                if first:
                    first = False
                else:
                    new = new.joinpath(part)
            self.description = str(new)
        else:
            self.description = str(result)

        if self.description == '.':
            self.description = ''

    def _parse_path_values(self, parse_data: List, path_string):

        """
        parse data [compiled.re,  dateFmt, re_group_keys,  scope_indicator].
        :return:
        """
        re_parse = parse_data[0].match(path_string)
        if re_parse:
            re_array = re_parse.groups()
            if parse_data[2] != 0:  # We are looking for a real date
                date_string = "".join(re_array[1:parse_data[2] + 1])
                try:
                    self.dates['date'] = datetime.strptime(date_string, parse_data[1])
                    self._set_path_description(Path(re_array[parse_data[2] + 1]))
                    return True
                except ValueError:  # pragma: no cover
                    logger.debug('Could not convert %s of %s to a date', date_string, self.path)
            else:
                self._set_path_description(Path(path_string))
                return True
        return False

    def set_date_and_description(self, significant_path: Path):
        """
        Use the various / ordered path parsers to get dates and descriptions
        :return:
        """
        path_str = str(significant_path)
        for value in FOLDER_PARSERS:
            if self._parse_path_values(value, path_str):
                if self.dates['date']:
                    if value[3] in ['Month', 'Day']:
                        self.dates['month'] = True
                    if value[3] == 'Day':
                        self.dates['day'] = True
                    break




    '''
    def rollup_files(self, destination: Path):
        """

        :param destination:
        :return:
        """
        for child in self.children:
            child.rollup_files(destination)

        files = [f for f in os.listdir(self.name) if os.path.isfile(os.path.join(self.name, f))]
        for file in files:
            if not destination.joinpath(file).exists():
                logger.debug('Moving %s to %s', self.name.joinpath(file), destination)
                print(f'Moving {self.name.joinpath(file)} to {destination}')
                os.rename(self.name.joinpath(file), destination.joinpath(file))
    '''


class FileCleaner(CleanerBase):

    """
    A class to encapsulate the regular file Path object that is going to be cleaned
    """

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        if self == other:  # Our files are the same
            return self.date < other.date
        return False

    def __gt__(self, other):
        if self == other:
            return self.date > other.date
        return False

    @property
    def is_valid(self) -> bool:
        return self.path.is_file() and self.path.stat().st_size != 0

    @property
    def is_small(self):
        """
        No reason for a normal file to be small
        :return: False
        """
        return False

    @property
    def date(self):
        """
        Should we consider path dates?
        :return:
        """
        if not self._date:
            self._date = datetime.fromtimestamp(int(os.stat(self.path).st_mtime))
        return self._date


class ImageCleaner(CleanerBase):
    """
    A class to encapsulate the image file Path object that is going to be cleaned
    """
    CONVERSION_SUFFIX = ['.'
                         'HEIC', ]

    def __init__(self, path_entry: Path):
        super().__init__(path_entry)

        self._image = None
        self._image_data = []
        pass

    def __eq__(self, other: ImageCT):
        """
        Use the image data to compare images
        :param other: The other end of equal
        :return:
        """
        result = super().__eq__(other)
        if not result and other.__class__.__name__ == self.__class__.__name__:
            self.load_image_data()
            other.load_image_data()
            return self.date == other.date and self.date
        return result

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
    def is_valid(self) -> bool:
        return self.path.is_file() and self.path.stat().st_size != 0

    @cached_property
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
                try:
                    temp = self._date = FN_DATE.match(self.path.stem).groups()
                    self._date = datetime(temp[0], temp[1], temp[2])
                except AttributeError:
                    pass
                except ValueError:
                    pass
                if not self._date:
                    self._date = self.folder.date if self.folder else None
            else:
                self._metadate = True
        return self._date

    # Ensure we have a date for the existing image
    def set_date(self):
        # original_file: Path, new_date: Union[datetime, None]):  # pragma: no cover
        """
        If we have a date, and we did not get it from the original image,  set the 'Digitized' date.

        :return: None
        """
        if not self._metadate and self.date:
            exif_dict = piexif.load(str(self.path))

            new_date = self.date.strftime("%Y:%m:%d %H:%M:%S")
            exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = new_date

            # Save changes
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, str(self.path))

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

    def convert(self, work_dir: Path, migrated_base: Optional[Path], remove: bool = True) -> ImageCT:  # pragma: win
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
        :param remove: default: True,  remove this file

        :return: self or a new object that's updated

        I think this also works with HEIC files
        """
        if self.path.suffix.upper() not in self.CONVERSION_SUFFIX:
            return self

        if platform.system() == 'Windows':
            # This option is not supported via GUI so no one should see this logger.error
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
                if 'type' in metadata and metadata['type'] == 'Exif':  # pragma: no branch
                    exif_dict = piexif.load(metadata['data'])
            if exif_dict:
                exif_bytes = piexif.dump(exif_dict)
                image.save(new_name, format("JPEG"), exif=exif_bytes)
                if migrated_base:
                    self.relocate_file(migrated_base, remove=remove, rollover=False)
                elif remove:
                    original_name.unlink()
                return ImageCleaner(Path(new_name))
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
                except ValueError:
                    logger.debug('Corrupt date data %s', self.path)  # pragma: no cover
            else:
                logger.debug('Could not find a date in %s', self.path)

        except piexif.InvalidImageDataError:
            logger.debug('Failed to load %s - Invalid JPEG/TIFF', self.path)
        except FileNotFoundError:
            logger.debug('Failed to load %s - File not Found', self.path)
