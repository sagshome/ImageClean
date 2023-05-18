"""
Base classes for cleaning objects
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

if platform.system() != 'Windows':  # pragma: no cover
    import pyheif  # pylint: disable=import-outside-toplevel, import-error

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
    assert not entry.is_dir()  # entry must be a file

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
                if os.stat(self.path).st_ino == os.stat(other.path).st_ino:
                    return True
                if os.stat(self.path).st_size == os.stat(other.path).st_size:
                    return cmp(self.path, other.path, shallow=False)
            except FileNotFoundError:
                logger.error('File %s or %s does not exists', self.path, other.path)
        return False

    def __lt__(self, other) -> bool:
        return False

    def __gt__(self, other) -> bool:
        return False

    def __ne__(self, other) -> bool:
        return not self == other

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
        return the internal value for date, if one exists
        """
        return self._date

    @property
    def folder(self) -> Optional[FolderCT]:
        """
        Look up a cached folder for this element
        :return:
        """
        key = self.path.parent.as_posix()
        if key in output_folders:
            return output_folders[key]
        return None

    @property
    def is_small(self) -> bool:
        """
        A test for garbage files
        :return:
        """
        return False

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

    def register(self, base_folder: Path = None):
        """
        Register the existence of a file and update the folder count.
        :return:
        """

        if self.registry_key not in output_files:
            output_files[self.registry_key] = []
        output_files[self.registry_key].append(self)

        if base_folder and not self.folder:
            Folder(self.path.parent, base_folder, cache=True)

        if self.folder:
            self.folder.count += 1

    def de_register(self):
        """
        Remove yourself from the list of registered FileClean objects
        """
        if self.registry_key in output_files:
            new_list = []
            for value in output_files[self.registry_key]:
                if not id(value) == id(self):
                    new_list.append(value)
                else:
                    if self.folder:
                        self.folder.count -= 1
            if not new_list:
                del output_files[self.registry_key]
            else:
                output_files[self.registry_key] = new_list

    def is_registered(self, by_file: bool = False, by_path: bool = False, new_path: Path = None) -> bool:
        """
        Test for existing of a file
        :param by_file:   Ensure a match on the existing file
        :param by_path:   Ensure a match on the existing path
        :param new_path:  Ensure a match on this other path
        :return:  True if exists
        """
        by_path = True if new_path else by_path
        if not by_path and not by_file:
            return self.registry_key in output_files

        return len(self.get_registered(by_file, by_path, new_path)) > 0

    def get_registered(self, by_file: bool = False, by_path: bool = False, new_path: Path = None) -> List[CT]:
        """
        Retrieve an existing file object
        :param by_file:   Ensure a match on the existing file
        :param by_path:   Ensure a match on the existing path
        :param new_path:  Ensure a match on this other path
        :return:  object or None
        """
        result = []
        by_path = True if new_path else by_path

        if self.registry_key in output_files:
            path_to_test = new_path if new_path else self.path
            if path_to_test.is_file():
                path_to_test = path_to_test.parent
            for value in output_files[self.registry_key]:
                if by_file and by_path:
                    if self == value and value.path.parent == path_to_test:
                        result.append(value)
                elif by_path:
                    if value.path.parent == path_to_test:
                        result.append(value)
                elif by_file:
                    if self == value:
                        result.append(value)
                else:
                    result.append(value)
        return result

    # File manipulation

    def folder_base2(self, input_folder: FolderCT = None, no_date_base: Path = Path()) -> Path:
        # pylint: disable=too-many-branches
        """
        with input as a priority,  build an output path based on dates (folder year/file date) and description
        Result should look like
        YYYY/MM/DD or YYYY/Description or YYYY/MM/Description or YYYY/MM/DD/Description or Nothing

        May 15th/2023 - I have an issue with _NoDate folders/<sub_folder>  they keep growing.   To get around this
        I am going to implement no duplicates on the path.   So you cant have .../vacation/vacation/etc///

        :param input_folder - The folder from importing of where files without a date should go
        :param no_date_base - The path base of where files without a date should go
        :return:
        """
        def strip_part(path_description: str) -> str:
            desc_as_path = Path(path_description)  # Work in paths to support Unix/Windows
            part_to_strip = str(no_date_base)
            result = Path()

            for path_part in desc_as_path.parts:
                if path_part != part_to_strip:
                    result = result.joinpath(path_part)
            return result

        folder = input_folder if input_folder else self.folder
        description: str = folder.description if folder else None  # folder.description may also be None
        dates: Dict = folder.dates if folder else None  # existing date w/description 2022/picnic

        for existing in self.get_registered(by_file=True):   # See if we have any duplicates of this input file.
            folder: FolderCT = existing.folder if existing.folder else None
            if folder and folder.description and not description:   # If this folder has a description and we don't
                description = folder.description                    # Then use this folder's description
                dates = folder.dates if folder.date else dates      # and this folders date if it has date

        if description:
            description = strip_part(description) if no_date_base != Path() else description
            if dates and dates['date']:
                path = Path(dates['date'].strftime('%Y'))
                if dates['day']:
                    path = path.joinpath(f"{dates['date'].strftime('%m-%d')} {description}")
                elif dates['month']:
                    path = path.joinpath(f"{dates['date'].strftime('%m')} {description}")
                else:
                    path = path.joinpath(description)
            elif self.date:
                path = Path(self.date.strftime('%Y'))
                path = path.joinpath(description)
            else:
                path = no_date_base
                path = path.joinpath(description)
        else:  # No Description
            if dates and dates['date']:
                path = Path(dates['date'].strftime('%Y'))
                if dates['month']:
                    path = path.joinpath(dates['date'].strftime('%m'))
                if dates['day']:
                    path = path.joinpath(dates['date'].strftime('%d'))
            elif self.date:
                path = Path(self.date.strftime('%Y')).\
                    joinpath(self.date.strftime('%m')).\
                    joinpath(self.date.strftime('%d'))
            else:
                path = no_date_base

        if not self.date and dates and dates['date']:
            self._date = dates['date']

        return path

    # pylint: disable=too-many-arguments
    def relocate_file(self, new_path: Path, base_folder: Path = None, remove: bool = False, rollover: bool = True,
                      register: bool = False):
        """
        :param new_path: A string representation of the folder
        :param base_folder: The root of the output folder
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
                    copied = True

            if not new_file.exists():
                try:
                    copyfile(str(self.path), new_file)
                    copied = True
                except PermissionError as error:  # pragma: no cover
                    logger.error('Can not write to %s - %s', new_path, error)

        if remove and copied:
            try:
                self.de_register()
                os.unlink(self.path)
            except OSError as error:   # pragma: no cover
                logger.debug('%s could not be removed (%s)', self.path, error)

        if copied:
            self.path = new_file
            self.set_date()

        if register and new_file and copied:
            self.register(base_folder=base_folder)

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

    def set_date(self):  # pragma: no cover
        """
        Just a stub,  nothing to see here - move along
        """
        pass  # pylint: disable=unnecessary-pass


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

    def __init__(self, path_entry: Path, base_entry: Path, internal: bool = False, cache: bool = True):
        super().__init__(path_entry)
        self.internal = internal  # Bool to indicate this is an internal folder so no need to process it

        self.dates: Dict = {
            'date': None,  # the time stamp (if any)
            'month': False,  # set to True if the date really contained a month (by default month is 1)
            'day': False,  # set to True if the date really contained a day (by default day is 1)
        }
        self.description: str = ''
        self.count: int = 0  # How many files in this folder
        self.children: List[FolderCT] = []  # Sub-folders.

        self.set_date_and_description(self.path.relative_to(base_entry))

        key = self.path.as_posix()
        # May 3rd,  added and self.date to if.
        # if cache and key not in output_folders and self.date:  # Only cache output folders and they must have a date
        if cache and key not in output_folders:
            output_folders[key] = self

        if internal:
            self.description = ''  # Override description on internal folders

        # print(f'{self.path} : {self.date} : {self.count} : {self.description} : {base_entry}')

    @classmethod
    def is_internal(cls, path: Path) -> bool:
        """
        Check the cache to see if a FolderData instance exists and if it is an internal folder
        :param path:
        :return:
        """
        key = path.as_posix()
        if key in output_folders and output_folders[key].internal:
            return True
        return False

    @classmethod
    def get_folder(cls, path: Path) -> Union[FolderCT, None]:
        """
        Parse the cache and return a Folder instance (if it exists)
        :param path:
        :return:
        """
        path_str = path.as_posix()
        if path_str in output_folders:
            return output_folders[path_str]
        return None

    @property
    def date(self) -> Optional[datetime]:
        """
        Return a datetime value if it exists on this folder (using parsing not stat)
        :return:
        """
        return self.dates['date']

    def _set_path_description(self, path_string):
        result = Path()
        path = Path(path_string)
        for part in path.parts:
            if part != '.' and not (len(part) == 22 and part.find(' ') == -1):

                try:
                    int(CLEAN.sub('', part.rstrip()))
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


class FileCleaner(CleanerBase):

    """
    A class to encapsulate the regular file Path object that is going to be cleaned
    """

    def __lt__(self, other):  # pragma: no cover
        if self == other:  # Our files are the same
            return self.date < other.date
        return False

    def __gt__(self, other):  # pragma: no cover
        if self == other:
            return self.date > other.date
        return False

    @property
    def is_valid(self) -> bool:  # pragma: no cover
        """
        Test if it is a file and it's not 0
        :return:
        """
        return self.path.is_file() and self.path.stat().st_size != 0

    @property
    def is_small(self):  # pragma: no cover
        """
        No reason for a normal file to be small
        :return: False
        """
        return False

    @property
    def date(self):  # pragma: no cover
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

    def __eq__(self, other: ImageCT):
        """
        Use the image data to compare images
        :param other: The other end of equal
        :return:
        """
        result = super().__eq__(other)
        if not result and other.__class__.__name__ == self.__class__.__name__:
            return self.image_data == other.image_data
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
        """
        Test if a file is valid (is a file and not 0
        :return:
        """
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
    def date(self) -> Optional[datetime]:
        """
        return the cached date or go and try and fetch it
        :return: datetime or None
        """
        if not self._date:
            self._date = self.get_date_from_image()
            if not self._date:  # Short circuit to find a date
                try:
                    temp = self._date = FN_DATE.match(self.path.stem).groups()
                    self._date = datetime(int(temp[0]), int(temp[1]), int(temp[2]))
                except AttributeError:  #os.stat(self.path).st_size == os.stat(other.path).st_size
                    pass
                except ValueError:  # pragma: no cover
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
            try:
                exif_dict = piexif.load(str(self.path))

                new_date = self.date.strftime("%Y:%m:%d %H:%M:%S")
                exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = new_date

                # Save changes
                exif_bytes = piexif.dump(exif_dict)
                piexif.insert(exif_bytes, str(self.path))

            except piexif.InvalidImageDataError:
                pass  # This is to be expected

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
        else:  # pragma: no cover
            original_name = self.path
            new_name = work_dir.joinpath(f'{self.path.stem}.jpg')

            if new_name.exists():
                new_name.unlink()
                logger.debug('Cleaning up %s - It already exists', new_name)

            exif_dict = None
            heif_file = pyheif.read(original_name)
            image = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw",
                                    heif_file.mode, heif_file.stride)
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
            except AttributeError as error:
                logger.error('Conversion error: %s - Reason %s is no metadata attribute', self.path, error)
        return self

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
                    logger.debug('Corrupt date data %s', self.path)
            else:
                logger.debug('Could not find a date in %s', self.path)

        except piexif.InvalidImageDataError:
            logger.debug('Failed to load %s - Invalid JPEG/TIFF', self.path)
        except FileNotFoundError:
            logger.debug('Failed to load %s - File not Found', self.path)
