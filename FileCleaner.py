import logging
import os
import piexif
import pyheif

from datetime import datetime
from filecmp import cmp
from pathlib import Path
from PIL import Image
from shutil import copyfile
from typing import List, Dict, Optional, TypeVar
from FolderCleaner import FolderCleaner

os.environ.get("HOME")


FileCT = TypeVar("FileCT", bound="FileCleaner")


class FileCleaner:
    """
    A class to encapsulate the Path object that is going to be cleaned
    """

    duplicate_hash: Dict[str, List[FileCT]] = {}  # This hash is used to store processed files

    conversion_dict = {"JPEG": "jpg"}

    # Inter-instance data
    files_to_convert = ['.HEIC', ]
    picture_files = ['JPG', 'HEIC', 'AVI', 'MP4', 'THM', 'RTF', 'PNG', 'JPEG', 'MOV', 'TIFF']
    files_to_update_date = ['JPG', 'THM', 'jpeg', 'tiff']
    image_files = ['JPG', 'HEIC', 'PNG', 'TIFF']
    movie_files = ['MOV', 'AVI', 'MP4']

    all_pictures = []
    all_update = []
    all_images = []
    all_movies = []

    def __init__(self, file_entry: Path, folder: FolderCleaner = None):

        if isinstance(file_entry, str):
            file_entry = Path(file_entry)

        # This is stuff that is done once only
        if len(self.all_update) == 0:
            for file_type in self.picture_files:
                self.all_pictures.append(f'.{file_type.upper()}')
                self.all_pictures.append(f'.{file_type.lower()}')
            for file_type in self.files_to_update_date:
                self.all_update.append(f'.{file_type.upper()}')
                self.all_update.append(f'.{file_type.lower()}')
            for file_type in self.image_files:
                self.all_images.append(f'.{file_type.upper()}')
                self.all_images.append(f'.{file_type.lower()}')
            for file_type in self.movie_files:
                self.all_movies.append(f'.{file_type.upper()}')
                self.all_movies.append(f'.{file_type.lower()}')

        self.file = file_entry
        try:
            stat = os.stat(file_entry)
            self.size = stat.st_size
        except FileNotFoundError:
            self.size = 0
        self.date = None
        self.folder = folder

    def __eq__(self, other):
        """
        If the name (regardless of case) and file size are the same we are likely the same.
        :param other:
        :return:
        """
        return self.size == other.size and self.file.name.upper() == other.file.name.upper()

    def __ne__(self, other):
        return not self == other

    @property
    def just_name(self):
        return self.file.name[:len(self.file.name) - len(self.file.suffix)]

    @property
    def just_path(self):
        full_path = str(self.file)
        return full_path[:len(full_path) - len(self.file.suffix)]

    @property
    def just_top_folder(self):
        return self.file.parts[len(self.file.parts) - 2]

    def conversion_filename(self, conversion_type: str = "JPEG") -> str:
        return f'{self.just_path}.{self.conversion_dict[conversion_type]}'

    def convert(self, conversion_type: str = "JPEG") -> bool:
        """

        Convert the existing file,  and save the results in new_path
        :param conversion_type:  what we are converting too
        :return: bool,  if the conversion worked (or would have)
        """

        if self.file.suffix and self.file.suffix in self.files_to_convert:
            logging.debug(f'Convert {self.file} to {conversion_type}')
            if self.file.suffix == '.HEIC':
                return self._heif_to_jpg(conversion_type)
            else:
                assert False, f'Unable to support conversion for type {self.file.suffix}'

    def date_from_structure(self) -> datetime:
        """
        Last ditch attempt to find a timestamp of this file based on name and/or structure
        :return: Datetime or None if we failed
        """

        def parser(word, date_parser, split):
            """

            :param word: Want we are working on
            :param date_parser:  Date parse string
            :param split:  What to split on (optional)
            :return: Datetime or None
            """

            if split:
                word = word.split(split)[0]
            try:
                return datetime.strptime(word, date_parser)
            except ValueError:
                return None

        just_name = self.file.name[:len(self.file.name) - len(self.file.suffix)]
        value = parser(just_name, '%Y-%m-%d %H.%M.%S', None)
        if not value:
            value = parser(just_name, '%Y%m%d_%H%M%S', '_IMG_')

        if not value:  # Try and process the parent folder
            value = self.folder.folder_time
        if not value:
            logging.debug(f'No structure date found for {self.file.name} of {self.folder.path}')
        return value

    def de_register(self):
        """
        Remove yourself from the the list of registered FileClean objects
        """
        if not self.is_registered():
            logging.error(f'Trying to remove non-existent {self.file}) from duplicate_hash')
        else:
            new_list = []
            key = self.file.name.upper()
            for value in self.duplicate_hash[key]:
                if not value == self:
                    new_list.append(value)
            if not new_list:
                del self.duplicate_hash[key]
            else:
                self.duplicate_hash[key] = new_list

    def is_registered(self, by_path: bool = False, by_file: bool = False, alternate_path: Path = None) -> bool:
        value = self.get_registered(by_file=by_file, by_path=by_path, alternate_path=alternate_path)
        if value:
            return True
        return False

    def register(self):
        if self.is_registered(by_path=True, by_file=True):
            logging.error(f'Trying to re_register {self.file})')
        else:
            key = self.file.name.upper()
            if key not in self.duplicate_hash:
                self.duplicate_hash[key] = []
            self.duplicate_hash[key].append(self)

    @staticmethod
    def un_register(file_path: Path):

        entity = FileCleaner(file_path)
        duplicate = entity.get_registered(by_path=True, by_file=False)
        if duplicate:
            duplicate.de_register()
        else:
            logging.error(f'Try to un_register {file_path}(not registered)')

    @staticmethod
    def re_register(old_path: Path, new_path: Path):
        entity = FileCleaner(old_path)
        entity = entity.get_registered(by_path=True, by_file=False)
        if entity:
            entity.de_register()
            entity.file = new_path
            entity.register()
        else:
            logging.error(f'Try to re_register {old_path}(not registered) with {new_path}')

    def get_registered(self, by_path: bool = False, by_file: bool = False, alternate_path: Path = None)\
            -> Optional[FileCT]:
        key = self.file.name.upper()
        new_path = alternate_path if alternate_path else self.file.parent
        if key in self.duplicate_hash:
            for entry in self.duplicate_hash[key]:
                if by_file:
                    logging.debug(f'Comparing {entry.file} to {self.file}')
                    try:
                        found_file = cmp(entry.file, self.file)
                    except:
                        pass
                else:
                    found_file = True
                if by_path:
                    found_path = str(entry.file.parent) == str(new_path)
                else:
                    found_path = True
                if found_path and found_file:
                    return entry

        # todo:   This is bug,  not sure why I had it here
        # new_path = new_path if new_path else self.file.parent
        # if key in self.duplicate_hash:
        #     for entry in self.duplicate_hash[key]:
        #         if entry.file.parent == new_path:
        #             return entry
        return None

    def get_new_path(self, base: Path, invalid_parents=None) -> Path:
        """
        Using the time stamp and current location build a directory path to where this
        file should be moved to.
        :param: base,  is the root directory to build the new path from
        :invalid_parents: A list of strings components that should be excluded from any new path
        :return:  A Path representing where this file should be moved to
        """

        if invalid_parents is None:
            invalid_parents = []

        description = self.folder.recursive_description_lookup('', invalid_parents) if self.folder else None
        if not self.date and not self.folder.folder_time:
            return Path(f'{base}{os.path.sep}{description}')

        # Bug... all folders have a time.
        if self.date:
            year = self.date.year
            month = self.date.month
            day = self.date.day
        elif self.folder and self.folder.folder_time:
            year = self.folder.folder_time.year
            month = self.folder.folder_time.month
            day = self.folder.folder_time.day

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

    def _heif_to_jpg(self, conversion_type: str = "JPEG") -> bool:
        """
        :param conversion_type:  Only JPEG for now
        :return: bool - True if successful
        :return:

        I think this also works with HEIC files
        """
        if conversion_type not in self.conversion_dict:
            logging.error(f'Can not convert to type {conversion_type} - Not supported')
            return False

        new_name = f'{self.just_path}.{self.conversion_dict[conversion_type]}'
        if os.path.exists(new_name):
            logging.debug(f'Can not convert {self.file} to {new_name} - It already exists')
            return False  # A better copy of me already exists

        heif_file = pyheif.read(self.file)

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
        except AttributeError as e:
            logging.error(f'Conversion error: {self.file} - Reason {e} is no metadata attribute')
            return False

        if exif_dict:
            exif_bytes = piexif.dump(exif_dict)
            new_name = f'{self.just_path}.{self.conversion_dict[conversion_type]}'
            image.save(new_name, format(conversion_type), exif=exif_bytes)
        return True

    @property
    def is_valid(self) -> bool:
        if self.size == 0:
            logging.debug(f'is valid - false - {self.file} - Reason size is {self.size}')
            return False
        return True

    def update_image(self):
        """
        Update an image file with the data provided
        :return: None
        """

        if self.file.suffix not in self.all_update:
            return

        changed = False
        try:
            exif_dict = piexif.load(str(self.file))
            logging.debug(f'Success loading {self.file}')
            if self.date:
                new_date = self.date.strftime("%Y:%m:%d %H:%M:%S")
                exif_dict['0th'][piexif.ImageIFD.DateTime] = new_date
                exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = new_date
                exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = new_date
                changed = True
            if changed:
                exif_bytes = piexif.dump(exif_dict)
                piexif.insert(exif_bytes, str(self.file))

        except piexif.InvalidImageDataError:
            logging.debug(f'Failed to load {self.file} - Invalid JPEG/TIFF')
        except FileNotFoundError:
            logging.error(f'Failed to load {self.file} - File not Found')

    def get_date_from_image(self):
        """
        Given an Image object,  attempt to extract the date it was take at
        :return: datetime
        """
        if self.file.suffix not in self.all_update:
            return None

        image_date = None
        try:
            exif_dict = piexif.load(str(self.file))

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
                    logging.debug(f'Corrupt date data {self.file}')
            else:
                logging.debug(f'Could not find a date in {self.file}')

        except piexif.InvalidImageDataError:
            logging.debug(f'Failed to load {self.file} - Invalid JPEG/TIFF')
        except FileNotFoundError:
            logging.debug(f'Failed to load {self.file} - File not Found')

    def relocate_file(self, path: Path, update: bool = True, remove: bool = False):
        """
        :param path: A string representation of the folder
        :param update: A boolean (default: True) when True instance has path/file information updated.
        :param remove: A boolean (default: False) Once successful on the relocate,   remove the original
        :return:
        """
        if not os.path.exists(path):
            self._make_new_path(path)

        new = Path(f'{path}{os.path.sep}{self.file.name}')

        logging.debug(f'Copy {self.file} to {new}')
        if os.path.exists(new):
            logging.debug(f'Will not overwrite {new}')
        else:
            copyfile(str(self.file), new)
        if remove:
            os.unlink(self.file)
        if update:
            self.file = new  # In case this entry is used again,  point to the new location.

    def rollover_name(self, register=True):
        """
        Allow up to 20 copies of a file before removing the oldest
        file.type
        file_0.type
        file_1.type
        etc
        :return:
        """

        if os.path.exists(self.file):
            logging.debug(f'Rolling over {self.file}')

            basename = self.file.name[:len(self.file.name) - len(self.file.suffix)]
            for increment in reversed(range(20)):
                old_path = f'{self.file.parent}{os.path.sep}{basename}_{increment}{self.file.suffix}'
                new_path = f'{self.file.parent}{os.path.sep}{basename}_{increment+1}{self.file.suffix}'
                if os.path.exists(old_path):
                    if os.path.exists(new_path):
                        os.unlink(new_path)
                        self.un_register(Path(old_path)) if register else None
                    os.rename(old_path, new_path)
                    self.re_register(Path(old_path), Path(new_path)) if register else None
            os.rename(self.file, f'{self.file.parent}{os.path.sep}{basename}_0{self.file.suffix}')
            if register:
                self.re_register(self.file, Path(f'{self.file.parent}{os.path.sep}{basename}_0{self.file.suffix}'))

    @staticmethod
    def _make_new_path(path: Path):
        parts = path.parts
        directory = None
        for part in parts[0:len(parts)]:
            directory = f'{directory}{os.path.sep}{part}' if not part == os.path.sep else os.path.sep
            if not os.path.exists(directory):
                os.mkdir(directory)
