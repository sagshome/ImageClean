import logging
import os
import re

from datetime import datetime
from pathlib import Path


class FolderCleaner:
    """
    A class for processing folders,  going to use it to load a default time for files in this directory
    """

    folder_hash = {}

    def __init__(self, path_entry: Path, root_directory: str):
        if not isinstance(path_entry, Path):
            path_entry = Path(path_entry)

        self.path = path_entry
        self.year = None
        self.month = None
        self.date = None
        self.description = None
        self.parent = None
        self.root_directory = root_directory
        try:
            self.stat = os.stat(path_entry)
        except FileNotFoundError:
            self.stat = {'st_size': 0}

        self.set_metadata_from_path_name(self.root_directory)
        descriptions = re.match('^([-_ ]*)(.*)', self.description) if self.description else None
        self.description = descriptions.groups()[1] if descriptions else None
        self.content_dates = []
        self.files = []

    @property
    def default_date(self):
        if not self.year:
            return None
        month = self.month if self.month else 1
        day = self.date if self.date else 1
        return datetime(self.year, month, day)

    def _set_folder_date_and_description(self,  regexp: str,  date_format: str, array_max: int):
        """
        This will set the date values (year, month, date) and the description based on regular expression
        parsing and datetime formatting.

        :param regexp:  The RE to pull the date values and description
        :param date_format:  The date format to use based on the RE
        :param array_max:  The number of elements to process for the date format
        :return:
        """
        re_parse = re.match(regexp, self.path.name)
        if re_parse:
            re_array = re_parse.groups()
            date_string = "".join(re_array[0:array_max])
            try:
                dates = datetime.strptime(date_string, date_format)
                self.year = dates.year
                self.month = dates.month if array_max >= 2 else None  # Since strptime will stick in 1 if no month
                self.date = dates.day if array_max == 3 else None  # Since strptime will stick in 1 in no date
                self.description = re_array[array_max].rstrip().lstrip()
            except ValueError:
                logging.debug(f'Could not convert {date_string} of {self.path.name} to a date')

    def set_metadata_from_path_name(self, master_directory):
        """
        Try and get a Year/Month/Date from the structure
        formats:
        DD-MMM-YYYY
        DD-MMM-YYYY - description
        YYYY_MM - description
        YYYY_MM_DD - description
        YYYY_MM_DDdescription
        YYYY-Description
        """

        if master_directory == str(self.path):
            return
        self._set_folder_date_and_description('^([0-9]{4}).([0-9]{2}).([0-9]{2})(.*)', '%Y%m%d', 3)
        if not self.year:
            self._set_folder_date_and_description('^([0-9]{2}).([a-zA-Z]{3}).([0-9]{4})(.*)', '%d%b%Y', 3)
        if not self.year:
            self._set_folder_date_and_description('^([0-9]{4}).([0-9]{2})(.+)', '%Y%m', 2)
        if not self.year:
            self._set_folder_date_and_description('^([0-9]{4})(.+)', '%Y%m', 1)
        if not self.year:
            self._set_folder_date_and_description('^([0-9]{8})-([0-9]{6})(.*)', '%Y%m%d-%H%M%S', 3)
        if not self.year:
            try:
                int(self.path.name)  # Already parsed by something - we can do it again
            except ValueError:
                # Weird clause - some program imported using derived garbage names
                if not ((len(self.path.name) == 21 or len(self.path.name) == 22) and self.path.name.find(' ') == -1):
                    if not re.match('^[0-9]{8}-[0-9]{6}', self.path.name):  # A time stamp so forget it.
                        self.description = self.path.name

    def recursive_description_lookup(self, current_description: str) -> str:
        """
        Recurse your parents to build up path based on descriptive folder names
        :param current_description:  a string with the build up path
        :return: a string with the path name based on os.path.sep and the various folder levels
        """
        if self.description:
            current_description = f'{os.path.sep}{self.description}{current_description}'
            if self.parent:
                current_description = self.parent.recursive_description_lookup(current_description)
        return current_description
