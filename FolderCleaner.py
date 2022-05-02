import logging
import os
import re

from datetime import datetime
from pathlib import Path
from typing import Optional, TypeVar


FolderCT = TypeVar("FolderCT", bound="FileCleaner")


class FolderCleaner:
    """
    A class for processing folders,  going to use it to load a default time for files in this directory
    """

    def __init__(self, path_entry: Path, root_directory: Path = None, parent: FolderCT = None):

        self.path: Path = path_entry
        self.root_directory: Path = root_directory

        self.folder_time: Optional[datetime] = None
        self.description: Optional[str] = None
        self.parent: Optional[FolderCT] = parent

        self.folder_time = self.get_date_from_path()  # A lot of re stuff, so just cache the value.
        self.description = self.get_description_from_path()

    def _get_date_from_path_name(self, regexp: str,  date_format: str, array_max: int) -> Optional[datetime]:
        re_parse = re.match(regexp, self.path.name)
        if re_parse:
            re_array = re_parse.groups()
            date_string = "".join(re_array[0:array_max])
            try:
                return datetime.strptime(date_string, date_format)
            except ValueError:
                logging.debug(f'Could not convert {date_string} of {self.path.name} to a date')
        return None

    def _get_description_from_path_name(self, regexp: str, array_max: int) -> Optional[str]:
        re_parse = re.match(regexp, self.path.name)
        if re_parse:
            re_array = re_parse.groups()
            return re_array[array_max].rstrip().lstrip()
        return None

    def get_date_from_path(self) -> Optional[datetime]:
        parser_values = [
            ['^([0-9]{4}).([0-9]{2}).([0-9]{2})(.*)', '%Y%m%d', 3],
            ['^([0-9]{2}).([a-zA-Z]{3}).([0-9]{4})(.*)', '%d%b%Y', 3],
            ['^([0-9]{4}).([0-9]{2})(.+)', '%Y%m', 2],
            ['^([0-9]{4})(.+)', '%Y%m', 1],
            ['^([0-9]{8})-([0-9]{6})(.*)', '%Y%m%d%H%M%S', 3]
        ]

        for exp, fmt, index in parser_values:
            folder_date = self._get_date_from_path_name(exp, fmt, index)
            if folder_date:
                return folder_date

        parse_tree = re.match('.*([0-9]{4}).([0-9]{1,2}).([0-9]{1,2})$', str(self.path))
        if parse_tree:
            try:
                return datetime(int(parse_tree.groups()[0]),
                                int(parse_tree.groups()[1]),
                                int(parse_tree.groups()[2]))

            except ValueError:
                pass

        # Use the parent date
        parent = self.parent
        while parent:
            if parent.folder_time:
                return self.parent.folder_time
            parent = parent.parent
        return None

    def get_description_from_path(self) -> Optional[str]:

        parser_values = [
            '^[0-9]{4}.[0-9]{2}.[0-9]{2}(.*)',
            '^[0-9]{2}.[a-zA-Z]{3}.[0-9]{4}(.*)',
            '^[0-9]{4}.[0-9]{2}(.+)',
            '^[0-9]{4}(.+)',
            '^[0-9]{8}-[0-9]{6}(.*)',
        ]

        description = None
        matched = False
        for exp in parser_values:
            re_parse = re.match(exp, self.path.name)
            if re_parse:
                description = re_parse.groups()[0]
                matched = True
                break

        if not description and not matched:
            # Weird clause - some program imported using derived garbage names
            if not ((len(self.path.name) == 21 or len(self.path.name) == 22) and self.path.name.find(' ') == -1):
                if not re.match('^[0-9]{8}-[0-9]{6}', self.path.name):  # A time stamp so forget it.
                    try:
                        int(self.path.name)  # a piece of a date folder tree yyyy/mm/dd
                    except ValueError:
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
