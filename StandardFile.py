import logging
import os
import re
import sys

from datetime import datetime
from shutil import copy2
from typing import List, Dict, TypeAlias

from pathlib import Path


from CleanerBase import CleanerBase, APPLICATION, FolderCT, FileCT


NORMALIZE_FILENAME = re.compile(r"""
   \ *\( \d+ \)                     # (a) numbers inside parentheses like (23) and leading space(s)
  | (_(?:[0-9]|1[0-9]|20))+(?=\.)   # (b) _0 to _20 (as many as exist) when followed by a dot
  | [^a-zA-Z0-9_\-. ]*              # (c) Just these characters
  | ^\.*                            # (d) leading '.' since it hides the output
    """, re.VERBOSE)

logger = logging.getLogger(APPLICATION)


FileCache: TypeAlias = Dict[str, Dict[str, List[FileCT]]]  # must be a posix path string will be a folder key


class StandardFile(CleanerBase):

    """
    A class to encapsulate the regular file Path object that is going to be cleaned
    """

    def __str__(self):
        size = self.stat.st_size if self.stat else '-'
        folder = self.folder.significant_path if self.folder else 'No Folder'

        return f'{self.normalized_name}:{size} {self.path.name} of {folder}'

    def __init__(self, path_entry: Path, folder: FolderCT = None):
        super().__init__(path_entry)
        self.normalized_name: str = NORMALIZE_FILENAME.sub('', self.path.name).lower()
        self.folder: FolderCT | None = folder if folder else None
        self._date: datetime | None = None
        self._metadate: bool = False

    def __eq__(self, other: FileCT) -> bool:
        """ Same class, same file, same size"""
        if self.__class__ == other.__class__:
            if self.stat.st_ino == other.stat.st_ino:
                return True
            return self.stat.st_size == other.stat.st_size and self.normalized_name == other.normalized_name
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

    def adjust_cache(self, new_destination: Path, cache: FileCache):
        if self.path == new_destination:
            return
        self.clear_cache(cache)
        self.path = new_destination
        self.normalized_name = NORMALIZE_FILENAME.sub('', self.path.name).lower()
        self.cache(cache)

    def cache(self, cache: FileCache):
        """
        cache[normalized_name][path.name][FileCT...]  (each file will have a 'folder.score' to further refine)
        """

        if self.normalized_name not in cache:
            cache[self.normalized_name] = {}
        if self.path.name not in cache[self.normalized_name]:
            cache[self.normalized_name][self.path.name] = []
        cache[self.normalized_name][self.path.name].append(self)

    def clear_cache(self, cache: FileCache):
        if self.normalized_name in cache and self.path.name in cache[self.normalized_name]:
            for element in cache[self.normalized_name][self.path.name]:
                if element == self:
                    cache[self.normalized_name][self.path.name].remove(self)
            if not len(cache[self.normalized_name][self.path.name]):
                del cache[self.normalized_name][self.path.name]
            if not len(cache[self.normalized_name]):
                del cache[self.normalized_name]

    def convert(self, work_dir:Path, output_dir: Path, output_cache: FileCache = None, keep: bool = True) -> FileCT:
        """
        Stub,  used only with image files
        :return:
        """
        return self

    @property
    def date(self):  # pragma: no cover
        """
        Take the Modified time of this file since ctime (creation) is not readily available
        :return:
        """
        if not self._date:
            self._date = datetime.fromtimestamp(int(self.stat.st_mtime))
        return self._date

    def destination_path(self) -> Path:
        """
        using my folder as optional input build a path based on dates and descriptions
           * structure will be YYYY/MM
           * Folder dates come first, the use of the month is optional based on the pattern matched
           * When a file is used,  the format is always YYYY/MM
           * If a date is not available (applies to images only) - use NoDate
           * Folder descriptions are always added at the end.
        :return:
        """
        if self.folder and self.folder.date:
            path = Path(str(self.folder.date.year))
            if self.folder.has_month:
                path = path.joinpath(f"{self.folder.date.month:02d}")
        elif self.is_image and self.date and self._metadate:
            path = Path(str(self.date.year))
            path = path.joinpath(f"{self.date.month:02d}")
        else:
            path = Path()

        if self.folder and self.folder.description:
            path = path.joinpath(self.folder.description)

        return path

    def get_cache(self, cache: FileCache):
        if self.normalized_name in cache:
            for filename in cache[self.normalized_name]:
                for element in cache[self.normalized_name][filename]:
                    if element == self and self.folder == element.folder:
                        return element

    def get_cache_best(self, cache: FileCache) -> FileCT | None:
        """
        Get the best version of myself in the provided cache or none, if I don't exist in the cache
        :param cache:
        :return:
        """
        best = None
        if self.normalized_name in cache:
            for filename in cache[self.normalized_name]:
                for element in cache[self.normalized_name][filename]:
                    if self == element:
                        if not best or element > best:
                            best = element
        return best

    @classmethod
    def get_cache_by_path(cls, path: Path, cache: FileCache) -> FileCT or None:
        """
        get the cached by name value if any.
        """
        if path.exists:
            normalized_name: str = NORMALIZE_FILENAME.sub('', path.name).lower()
            size = path.stat().st_size
            if normalized_name in cache and path.name in cache[normalized_name]:
                for element in cache[normalized_name][path.name]:
                    if element.stat.st_size == size:
                        return element
        return None

    @property
    def is_small(self):
        return False

    @property
    def is_valid(self) -> bool:  # pragma: no cover
        """
        Test if it is a file and it's not 0
        :return:
        """
        return self.path.is_file() and self.stat.st_size != 0

    @classmethod
    def _move_file(cls, source: Path, destination: Path, cache: FileCache = None, keep: bool = True) -> str:
        """
        Move the file "source" to "destination" and if a cache is provided update the cache
        return a string with any errors or an empty string for success
        """

        try:
            copy2(source, destination)
            if cache:
                cached_value = StandardFile.get_cache_by_path(source, cache)
                if cached_value:
                    cached_value.adjust_cache(destination, cache)
                    cached_value.path = destination
            if not keep:
                source.unlink()
        except PermissionError:
            return 'Permission Error: Can not copy %s to %s' % (source, destination)

        return ''

    @classmethod
    def rollover_file(cls, destination: Path, cache: FileCache = None, max_copies: int = 20) -> str:
        """
        Allow up to 20 copies of a file before removing the oldest
        if cache is provided,  update the cache for all instances that were rolled over.
        :return:
        """
        logger.debug('Rolling over %s', destination)
        if not destination.exists():
            return 'Attempt to rollover non-existent file:%s' % destination

        for increment in reversed(range(max_copies)):  # 19 -> 0
            rollover_from = destination.parent.joinpath(f'{destination.stem}_{increment}{destination.suffix}')
            if rollover_from.exists():
                rollover_to = destination.parent.joinpath(f'{destination.stem}_{increment + 1}{destination.suffix}')
                res = cls._move_file(rollover_from, rollover_to, cache=cache, keep=False)
                if res:
                    return res

        rollover_to = destination.parent.joinpath(f'{destination.stem}_0{destination.suffix}')
        return cls._move_file(destination, rollover_to, cache=cache, keep=False)

    @property
    def refactored_name(self, filename: Path | None = None):
        """
        Given a filename,  refactor the name matching the case for both the filetype and filename based on the filename

        :return:
        """
        if self.path.stem.lower() == self.path.stem:
            return self.normalized_name  # Everything is already lowercase
        elif self.path.stem.upper() == self.path.stem:
            return self.normalized_name.upper()  # Make the name uppercase
        return NORMALIZE_FILENAME.sub('', self.path.name)  # Leave it camelcase

    def relocate_file(self, destination: Path, cache: FileCache = None, keep: bool = True, fix_date: bool = False, match_date: bool = False) -> str:
        """
        Copy self.path to <output_base>/<new_path>/self.path.name
            - doing a rollover if required
            - register if relocate is successful

        :param destination:  The complete Path you are moving to
        :param cache:        The output_cache you need to update (if any)
        :param keep:         Set to true if you wish for the original file (self) to be kept in place.
        :param fix_date:     Try and fix the internal date based on the external time stamp
        :param match_date:   Try and fix the external timestamp based on the internal date.
        :return:  A str containing any error messages
        """
        """
        """
        error = None
        if not self.path.exists():
            return 'Can not move a non-existent file:%s' % self.path

        if not destination.parent.exists():
            try:
                os.makedirs(destination.parent)
            except PermissionError:
                return 'Can not create folder %s' % destination.parent

        if destination == self.path:
            return 'Can not overwrite myself %s' % self.path

        if destination.exists():
            self.rollover_file(destination, cache=cache)

        if not destination.exists():  # Rollover if any, was successful

            if fix_date and self._metadate:
                error = self.update_date(destination, cache=cache, keep=keep)
                if not error:
                    match_date = True
            else:
                error = self._move_file(self.path, destination, cache=cache, keep=keep)

            if match_date and self.date and self._metadate:
                dt_epoch = self.date.timestamp()
                os.utime(destination, (dt_epoch, dt_epoch))
            if cache:
                self.cache(cache)
            return error
        else:
            return 'Will not overwrite %s! %s has not be relocated' % (destination, self.path)

    def update_date(self, destination: Path, cache: FileCache = None, keep: bool = True) -> str:
        """
        This method is overloaded in ImageFile, for here it is just the same move call
        """
        return self._move_file(self.path, destination, cache=cache, keep=keep)
