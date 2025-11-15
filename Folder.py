import logging
import re
import sys

from pathlib import Path
from typing import TypedDict, TypeVar
from datetime import datetime

from CleanerBase import CleanerBase, APPLICATION


logger = logging.getLogger(APPLICATION)

FolderCT = TypeVar("FolderCT", bound="Folder")  # pylint: disable=invalid-name
NON_DESCRIPTIVE_PATHS = ['Cleaner_ImageMovies', 'Cleaner_NoDate', 'Cleaner_Duplicates', 'Pictures', 'Dropbox', 'scans', 'pictures']

CLEAN = re.compile(r'^[ \-_]+')
SKIP_FOLDER = re.compile(r'^\d{8}-\d{6}$')


class FolderDateDict(TypedDict):
    date:  datetime | None  # the time stamp (if any)
    month: bool  # set to True if the date really contained a month (by default month is 1)
    day: bool  # set to True if the date really contained a day (by default day is 1)


class FolderDateExpression:
    expression: re.compile
    formatter: str | None
    groups: int | None
    date_type: str | None

    def __init__(self, expression, formatter=None, groups=None, date_type=None):
        self.expression = re.compile(expression)
        self.formatter = formatter
        self.groups = groups
        self.date_type = date_type

    def get_date(self, posix_path: Path.as_posix) -> datetime | None:
        re_parse = self.expression.match(posix_path)
        if re_parse:
            re_array = re_parse.groups()
            if self.groups:
                try:
                    return datetime.strptime("".join(re_array[:self.groups]), self.formatter)
                except ValueError:
                    logger.error('Could not parse datetime from %s using formatter %s' % (posix_path, self.formatter))
            return None

    def get_description(self, posix_path: Path.as_posix) -> Path:
        """
        Give a path, in the form of a posix string,  strip out any portions that are invalid based on:
            - NON_DESCRIPTIVE_PATHS
            - are exactly 22 characters long without spaces - a funky apply thing
            - is not a single .
        :param posix_path:
        :return:
        """
        result = Path()
        re_parse = self.expression.match(posix_path)
        if re_parse:
            re_array = re_parse.groups()
            if re_array:
                description_parts = Path(re_array[-1])  # The last group will be the description parts
                for part in description_parts.parts:  # Clean out junk
                    if part != '.' and not (len(part) == 22 and part.find(' ') == -1) and (part not in NON_DESCRIPTIVE_PATHS):
                        clean_part = CLEAN.sub('', part.rstrip())
                        try:
                            int(clean_part)  # Ignore directories that are not part of the date, and are strictly numeric
                        except ValueError:
                            if not SKIP_FOLDER.match(part):  # a Date folder looking like a string
                                result = result.joinpath(clean_part)

                if result.root:  # Will be true if the first part of the path is the root aka '/'  We don't want it
                    new = Path()
                    for part in result.parts[1:]:
                        new = new.joinpath(part)
                    result = new
                return result


FOLDER_PARSERS = [
    FolderDateExpression(r'.*([1-2]\d{3})[\\/\-_ ](\d{1,2})[\\/\-_ ](\d{1,2})(.*)', '%Y%m%d', 3, 'Day'),  # 1961/09/27
    FolderDateExpression(r'.*(\d{2})[\\/\-_ ]([a-zA-Z]{3})[\\/\-_ ](\d{2})(.*)', '%d%b%Y', 3, 'Day'),  # ...27-Sep-1961
    FolderDateExpression(r'.*([1-2]\d{3})[\\/\-_ ](\d{1,2})(.*)', '%Y%m', 2, 'Month'),  # ...1961 09
    FolderDateExpression(r'.*(\d{8})[_-]\d{6}(.*)', '%Y%m%d', 1, 'Day'),  # ...19610927-010203
    FolderDateExpression(r'.*([1-2]\d{3})(.*)', '%Y', 1, 'Year'),  # ...1961
    FolderDateExpression('(.*)')  # Whatever we have must be the description (if any)
]


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

    def __init__(self, path_entry: Path, base_entry: Path, folder: FolderCT = None):
        super().__init__(path_entry)
        self.parent: FolderCT = folder
        self.score = 0
        self.significant_path: Path.as_posix = self.path.relative_to(base_entry).as_posix()
        self.parser: FolderDateExpression | None = self.get_folder_parser()
        self._date: datetime | None = self.parser.get_date(self.significant_path) if self.parser else None
        self.description: Path = self.parser.get_description(self.significant_path) if self.parser else Path()

        if self.date:
            self.score = 50
            if self.parser.date_type == 'Month':
                self.score = 100
        self.score += len(self.description.parts) * 100

    def __str__(self):
        return self.significant_path

    def get_folder_parser(self) -> FolderDateExpression | None:
        for parser in FOLDER_PARSERS:
            if re.match(parser.expression, self.significant_path):
                return parser
        return None

    @property
    def path_base(self) -> Path:
        """
        Build the base components of the folders path as far as date/description
        :return:  Path
        """
        # This works because base starts out as "." and appending or prepending on "." does the right thing.
        base = Path()  # start with "."
        if self.parser:
            if self.parser.date_type:
                base = Path(self.date.strftime('%Y'))  # Replaces the "."
                if self.parser.date_type == 'Day' or self.parser.date_type == 'Month':
                    base = base.joinpath(Path(self.date.strftime('%m')))  # I stopped supporting 'Day' because the output was to granular

        return base.joinpath(self.description)  # An empty description is "." so it will have no effect

    '''
    def like_file(self, test_file: FileCT ) -> FileCT | None:
        for existing in self.children:
            if test_file.normalized_name == existing.normalized_name and test_file == existing:
                return existing
        return None
    '''
    @property
    def has_month(self):
        if self.parser:
            return self.parser.date_type == 'Month'
        return False
