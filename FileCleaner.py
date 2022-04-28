import logging
import os
import piexif
import pyheif

from datetime import datetime
from pathlib import Path
from PIL import Image
from shutil import copyfile

os.environ.get("HOME")


class FileCleaner:
    """
    A class to encapsulate the Path object that is going to be cleaned
    """

    conversion_dict = {"JPEG": "jpg"}

    # Inter-instance data
    files_to_convert = ['.HEIC', ]
    picture_files = ['JPG', 'HEIC', 'AVI', 'MP4', 'THM', 'PDF', 'RTF', 'PNG', 'JPEG', 'MOV', 'TIFF']
    files_to_update_date = ['JPG', 'THM', 'jpeg', 'tiff']
    image_files = ['JPG', 'HEIC', 'PNG', 'TIFF']
    movie_files = ['MOV', 'AVI', 'MP4']

    all_pictures = []
    all_update = []
    all_images = []
    all_movies = []

    def __init__(self, file_entry: Path):

        if not isinstance(file_entry, Path):
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
        self.parent = None

    def __eq__(self, other):
        if self.size == other.size and \
                self.file.name.upper() == other.file.name.upper() and \
                (
                        (self.date and other.date and self.date == other.date) or
                        (not self.date and not other.date)
                ):
            return True
        return False

    def __lt__(self, other):
        # note __lt__ is based on date so > means I was am less significant then
        if self.size == other.size and \
                self.file.name.upper() == other.file.name.upper() and \
                (self.date and other.date and self.date > other.date):
            return True
        return False

    def __gt__(self, other):
        # note __gt__ is based on date so < means I was am more significant then
        if self.size == other.size and \
                self.file.name.upper() == other.file.name.upper() and \
                (self.date and other.date and self.date < other.date):
            return True
        return False

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
        :param update_file: Used for debugging - default is Ture
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
            value = self.parent.default_date
        if not value:
            logging.debug(f'No structure date found for {self.file.name} of {self.file.parent}')
        return value

    def get_new_path(self, base: str) -> str:
        """
        Using the time stamp and current location build a directory path to where this
        file should be moved to.

        :return:  A string representing where this file should be moved to
        """

        description = self.parent.recursive_description_lookup('') if self.parent else None
        if not self.date and not self.parent.year:
            return f'{base}{os.path.sep}{description}'

        # Tough call,  but I trust humans - if the folder had a date it in,  trust it else trust the image
        year = self.parent.year if self.parent.year else self.date.year if self.date else None
        month = self.parent.month if self.parent.month else self.date.month if self.date else None
        day = self.parent.date if self.parent.date else self.date.day if self.date else None

        new = base
        if year and description:
            new = f'{new}{os.path.sep}{year}{os.path.sep}{description}'
        elif year:
            new = f'{new}{os.path.sep}{year}'
            if month:
                new = f'{new}{os.path.sep}{month}'
                if day:
                    new = f'{new}{os.path.sep}{day}'
        self._make_new_path(Path(new))
        return new

    def _heif_to_jpg(self, conversion_type: str = "JPEG") -> bool:
        """
        :param conversion_type:  Only JPEG for now
        :param update_file: boolean True will make a copy,  False will just do the work (used for testing)
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

    def relocate_file(self, path: str, update: bool = True, remove: bool = False):
        """
        :param path: A string representation of the folder
        :param update: A boolean (default: True) when True instance has path/file information updated.
        :param remove: A boolean (default: False) Once successful on the relocate,   remove the original
        :return:
        """
        if not os.path.exists(path):
            self._make_new_path(Path(path))

        new = f'{path}{os.path.sep}{self.file.name}'
        logging.debug(f'Copy {self.file} to {new}')
        if os.path.exists(new):
            logging.debug(f'Will not overwrite {new}')
        else:
            copyfile(str(self.file), new)
        if remove:
            os.unlink(self.file)
        if update:
            self.file = Path(new)  # In case this entry is used again,  point to the new location.

    def rollover_name(self, path_str: str):
        new_file = f'{path_str}{os.path.sep}{self.file.name}'  # This is the value of the new name
        new_path = Path(new_file)
        basename = new_path.name[:len(new_path.name) - len(new_path.suffix)]
        found = False
        for increment in range(100):  # More then 100 copies !  die
            new = f'{path_str}{os.path.sep}{basename}_{increment}{new_path.suffix}'
            if os.path.exists(new):
                continue
            os.rename(new_file, new)
            found = True
            break
        assert found, f"Duplicate name update exceeded for {new_file}"

    @staticmethod
    def _make_new_path(path: Path):
        parts = path.parts
        directory = None
        for part in parts[0:len(parts)]:
            directory = f'{directory}{os.path.sep}{part}' if not part == os.path.sep else os.path.sep
            if not os.path.exists(directory):
                os.mkdir(directory)
