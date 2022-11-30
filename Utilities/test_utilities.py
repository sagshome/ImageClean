"""
Just some things to make testing easier
"""
from datetime import datetime
from os import makedirs, walk
from pathlib import Path
from shutil import copyfile
from typing import Union

from piexif import ImageIFD, ExifIFD, dump, insert, load
from PIL import Image, ImageDraw

DATE_SPEC = datetime(1961, 9, 27)
DIR_SPEC = Path(str(DATE_SPEC.year)).joinpath(str(DATE_SPEC.month)).joinpath(str(DATE_SPEC.day))
DEFAULT_NAME = 'file.jpg'

def copy_file(in_file: Path, out_path: Path, new_name: str = None) -> Path:
    """

    :param in_file:
    :param out_path:
    :param new_name:
    :return:
    """
    if not out_path.exists():
        makedirs(out_path)

    new_name = in_file.name if not new_name else new_name
    new_path = out_path.joinpath(new_name)
    copyfile(str(in_file), new_path)

    return new_path


def count_files(path: Path):
    """

    :param path:
    :return:
    """
    count = 0
    for _, _, files_list in walk(path):
        for _ in files_list:
            count += 1
    return count


def create_file(name: Path, data: str = None, empty: bool = False) -> Path:
    """
    create a text file
    :param name:
    :param data:
    :param empty:
    :return:
    """
    if not name.parent.exists():
        makedirs(name.parent)

    with open(name, 'w+', encoding='utf-8') as file:
        if not empty:
            if not data:
                file.write(str(name))
            else:
                file.write(data)
    return name


def create_image_file(path: Path, date: Union[datetime, None], text: str = None, small: bool = False):
    """
    Use this to create an Image File  (It will respect the type..., use text to make unique)
    :param path:  -> what / where to save the image to - if no name is provided,  it will be file.jpg
    :param date: -> the datetime to set,  None has not date date
    :param text: -> Data to write into the image,  default is path.name
    :param small:  Set the image size to 360x360
    :return:
    """

    if not path.suffix:
        path = path.joinpath(DEFAULT_NAME)

    if not path.parent.exists():
        makedirs(path.parent)

    size = (360, 360) if small else (400, 400)
    text = text if text else path.stem
    exif_dict = {}

    canvas = Image.new('RGB', size, 'white')
    img_draw = ImageDraw.Draw(canvas)
    img_draw.text((70, 250), text, fill='green')
    if date:
        exif_dict['0th'] = {}
        exif_dict['0th'][ImageIFD.DateTime] = date.strftime("%Y:%m:%d %H:%M:%S")
    canvas.save(path, exif=dump(exif_dict))
    return path


def set_date(original_file: Path, new_date: Union[datetime, None]):  # pragma: no cover
    """
    Given a physical file,  move the file to the input directory
    original_file:  The file to process
    new_date: date_string to put into file
    move_to_input: If set,  copy the file to this location.
    :return: None
    """
    # Note,  currently not used (replaced with create_image_file)
    exif_dict = load(str(original_file))
    if not new_date:
        if ImageIFD.DateTime in exif_dict['0th']:
            del exif_dict['0th'][ImageIFD.DateTime]
        if ExifIFD.DateTimeOriginal in exif_dict['Exif']:
            del exif_dict['Exif'][ExifIFD.DateTimeOriginal]
        if ExifIFD.DateTimeDigitized in exif_dict['Exif']:
            del exif_dict['Exif'][ExifIFD.DateTimeDigitized]
    else:
        new_date = new_date.strftime("%Y:%m:%d %H:%M:%S")
        exif_dict['0th'][ImageIFD.DateTime] = new_date
        exif_dict['Exif'][ExifIFD.DateTimeOriginal] = new_date
        exif_dict['Exif'][ExifIFD.DateTimeDigitized] = new_date

    # Save changes
    exif_bytes = dump(exif_dict)
    insert(exif_bytes, str(original_file))
