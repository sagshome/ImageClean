import imagehash
import logging
import piexif
import platform
import sys

from datetime import datetime
from PIL import Image, UnidentifiedImageError
from pathlib import Path

try:
    import pyheif  # pylint: disable=import-outside-toplevel, import-error
    pass
except ModuleNotFoundError:
    pass

from StandardFile import StandardFile, APPLICATION, FileCache
from CleanerBase import FolderCT, FileCT

logger = logging.getLogger(APPLICATION)


class ImageFile(StandardFile):
    def __init__(self, path_entry: Path, folder: FolderCT = None):
        super().__init__(path_entry, folder)
        self._perceptual_hash: str = ''
        self._read_tried: bool = False

    def __eq__(self, other: FileCT) -> bool:
        """ Same class, same file, same content"""
        if self.__class__ == other.__class__:
            if self.stat.st_ino == other.stat.st_ino:
                return True
            if self.normalized_name == other.normalized_name and self.stat.st_size == other.stat.st_size:
                return True
            return self.perceptual_hash == other.perceptual_hash
        return False

    def __lt__(self, other: FileCT):
        """

        :param other:
        :return:
        """
        if self == other:  # Our files are the same
            if self.folder and other.folder:
                return self.folder.score < other.folder.score
            return self.date > other.date
        return False

    def __gt__(self, other):
        if self == other:
            if self.folder and other.folder:
                return self.folder.score > other.folder.score
            return self.date < other.date
        return False

    def convert(self, work_dir: Path, output_dir: Path, output_cache: FileCache = None, keep: bool = True):
        """
        Convert an image file to jpg file, writing the output to the destination path
           - Only HEIC format support.

        :param work_dir:  Temporary directory to write the jpg file to
        :param output_dir: Path to write output jpg file to
        :param output_cache: The FileCache to update with the converted file
        :param keep:  If true, the original file if moved to destination/migration
        :return: A ImageFile object for the new file
        """
        # Notes,
        #   Can not do the conversion directly to the destination because we need to first see if it is already converted.

        if not self.path.suffix.upper() == '.HEIC':
            return self

        if platform.system() == 'Windows':
            # This option is not supported via GUI so no one should see this logger.error
            logger.error('Conversion from HEIC is not supported on Windows')
            return self

        original_name = self.path
        new_name = work_dir.joinpath(f'{self.path.stem}.jpg')

        if new_name.exists():
            logger.debug('Cleaning up %s - It already exists in the temporary folder %s' % (new_name, work_dir))
            new_name.unlink()

        exif_dict = None

        try:
            pass
            heif_file = pyheif.read(original_name)
            # heif_file = 'Error'  # Just trying to debug an issue with pyinstaller
        except ValueError as error:
            logger.error('Conversion error: %s - Reason %s' % (self.path, error))
            return self

        image = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw", heif_file.mode, heif_file.stride)
        try:
            for metadata in heif_file.metadata or []:
                if 'type' in metadata and metadata['type'] == 'Exif':  # pragma: no branch
                    exif_dict = piexif.load(metadata['data'])
            if exif_dict:
                exif_bytes = piexif.dump(exif_dict)
                image.save(new_name, format("JPEG"), exif=exif_bytes)
        except AttributeError as error:
            logger.error('Conversion error: %s - Reason %s is no metadata attribute' % (self.path, error))
            return self
        new_obj = ImageFile(new_name, folder=self.folder)  # This is the object to return to relocation calling routing
        self._date = new_obj.date  # Use this to get the side effect of date/_metadate set.
        self.relocate_file(output_dir.joinpath('Migrations').joinpath(new_obj.destination_path()).joinpath(self.refactored_name), output_cache, keep=keep)
        return new_obj

    @property
    def date(self) -> datetime:  # pragma: no cover
        """
        Take the internal date from the image,  and if that fails treat this like a StandardFile
        """

        if not self._date:  # Get date from the image
            self.fetch_metadata()
            if self._date:
                return self._date
            return super().date
        return self._date

    def fetch_metadata(self):
        if not self._read_tried:
            self._read_tried = True
            image = self.open_image()
            if image:
                try:
                    self._perceptual_hash = str(imagehash.phash(image))
                except AttributeError:
                    logger.error('Can not get hash value from %s' % self.path)
                except OSError as e:
                    logger.error('Can not get hash value from %s - %s' % (self.path, e))

                date_string: bytes = b''
                if 'exif' in image.info:
                    exif_dict = piexif.load(image.info['exif'])
                    if exif_dict:
                        try:
                            date_string = exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal]
                        except KeyError:
                            try:
                                date_string = exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized]
                            except KeyError:
                                try:
                                    date_string = exif_dict['0th'][piexif.ImageIFD.DateTime]
                                except KeyError:
                                    pass

                if date_string:
                    try:
                        self._date = datetime.strptime(str(date_string, 'utf-8'), '%Y:%m:%d %H:%M:%S')
                        self._metadate = True
                    except ValueError:  # pragma: no cover
                        pass
                image.close()

    def open_image(self):

        try:
            return Image.open(self.path)
        except UnidentifiedImageError:
            logger.debug('Failed to load %s - Invalid JPEG/TIFF', self.path)
        except piexif.InvalidImageDataError:
            logger.debug('Failed to load %s - Invalid JPEG/TIFF', self.path)
        except FileNotFoundError:
            logger.debug('Failed to load %s - File not Found', self.path)
        return None

    @property
    def perceptual_hash(self) -> str:
        """
        Lookup and set the perceptual hash if it is not already defined
        :return: imagehash.ImageHash | None
        """
        if not self._perceptual_hash:
            self.fetch_metadata()
        return self._perceptual_hash

    def update_date(self, destination: Path, cache: FileCache = None, keep: bool = True) -> str:
        """
        Do the job of _move but instead update the image time and save the file
        """
        date_to_write = self.date
        if date_to_write and not self._metadate:  # _metadate, indicates the date is from the filesystem not the image
            image = self.open_image()
            if image:
                date_to_write = date_to_write.strftime("%Y:%m:%d %H:%M:%S")
                if 'exif' in image.info:
                    exif_dict = piexif.load(image.info["exif"])
                else:
                    exif_dict = {'Exif': {}, '0th': {}}
                exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = date_to_write
                exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = date_to_write
                exif_dict['0th'][piexif.ImageIFD.DateTime] = date_to_write
                exif_bytes = piexif.dump(exif_dict)
                image.save(destination, exif=exif_bytes, quality="keep")
                image.close()

            if cache:
                cached_value = self.get_cache(cache)
                if cached_value:
                    cached_value.adjust_cache(destination, cache)
                    cached_value.path = destination

            if not keep:
                self.path.unlink()
            return ''
        else:
            return self._move_file(self.path, destination, cache=cache, keep=keep)
