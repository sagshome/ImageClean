import logging
import platformdirs
import stat

from datetime import datetime
from pathlib import Path
from typing import Dict, List, TypedDict, TypeVar

AUTHOR = "scott.sargent61@gmail.com"
APPLICATION = "Cleaner"
VERSION = "1.1"

IGNORE_FILES = ['.tar', '.rar', '.zip', '.gzip']
PICTURE_FILES = ['.jpg', '.jpeg', '.tiff', '.tif', '.png', '.bmp', '.heic']
MOVIE_FILES = ['.mov', '.avi', '.mp4']

logger = logging.getLogger(APPLICATION)

FileCT = TypeVar("FileCT", bound="StandardFile")  # pylint: disable=invalid-name
ImageCT = TypeVar("ImageCT", bound="ImageFile")  # pylint: disable=invalid-name
FolderCT = TypeVar("FolderCT", bound="Folder")  # pylint: disable=invalid-name


cached_by_size: Dict[int, List[str]] = {}       # Key stat.st_size, then a list of filenames with that size
cached_by_name: Dict[str, Dict[str, Dict[int,  List[FileCT]]]] = {}  # Key normalized name, then actual name, then stat.st_size
# cached_by_folder: Dict[str, FolderCT] = {}      # Key significant folder str (full path, less base)
cached_duplicates: List[Path] = []


def config_dir(appname: str = APPLICATION) -> Path:
    config_data_dir = Path(platformdirs.user_config_dir(appname, AUTHOR, VERSION))
    config_data_dir.mkdir(parents=True, exist_ok=True)
    return config_data_dir


def log_dir(appname: str = APPLICATION) -> Path:
    log_data_dir = Path(platformdirs.user_log_dir(appname, AUTHOR, VERSION))
    log_data_dir.mkdir(parents=True, exist_ok=True)
    return log_data_dir


def user_dir(appname: str = APPLICATION) -> Path:
    user_data_dir = Path(platformdirs.user_data_dir(appname, AUTHOR, VERSION))
    user_data_dir.mkdir(parents=True, exist_ok=True)
    return user_data_dir


class CleanerBase:
    """
    A class to encapsulate the Path object that is going to be cleaned
    """
    def __init__(self, path_entry: Path):
        self.path: Path = path_entry
        self.parent: FolderCT | None = None
        self.stat: stat = 0

        try:
            self.stat: stat = self.path.stat()
        except FileNotFoundError:
            pass  # Not really a file

        self._date = None  # Only lookup once

    def __eq__(self, other) -> bool:
        return self.__class__ == other.__class__

    def __lt__(self, other) -> bool:
        return False

    def __gt__(self, other) -> bool:
        return False

    def __ne__(self, other) -> bool:
        return not self == other

    @property
    def date(self) -> datetime | None:
        """
        return the internal value for date, if one exists
        """
        return self._date

    @property
    def is_file(self) -> bool:
        if self.stat:
            return stat.S_ISREG(self.stat.st_mode)
        return False

    @property
    def is_dir(self) -> bool:
        if self.stat:
            return stat.S_ISDIR(self.stat.st_mode)
        return False

    @classmethod
    def is_ignored(cls, path: Path) -> bool:
        if path.suffix.lower() in IGNORE_FILES:
            return True
        return False

    @classmethod
    def is_image(cls, path: Path) -> bool:
        if path.suffix.lower() in PICTURE_FILES:
            return True
        return False

    @classmethod
    def is_movie(cls, path: Path) -> bool:
        if path.suffix.lower() in MOVIE_FILES:
            return True
        return False
