"""
Run the actual image cleaning
"""
import asyncio
# pylint: disable=line-too-long

import logging
import os
import pickle
import re
import sys
import tempfile

from copy import deepcopy
from pathlib import Path
from typing import Optional, Union, Dict, List, TypeVar

sys.path.append('.')
# pylint: disable=import-error wrong-import-position
from backend.cleaner import CleanerBase, ImageCleaner, FileCleaner, Folder, make_cleaner_object, PICTURE_FILES, MOVIE_FILES

logger = logging.getLogger('Cleaner')  # pylint: disable=invalid-name

NEW_FILE: int = 0
EXACT_FILE: int = 1
LESSER_FILE: int = 2
GREATER_FILE: int = 3
SMALL_FILE: int = 4

EXACT: int = 0
GREATER: int = 1
LESSER: int = 2

WARNING_FOLDER_SIZE = 100  # Used when auditing directories,  move then 100 members is a Yellow flag
MAXIMUM_FOLDER_SIZE = 50  # Date based folder,  more than MAX,  create a child
"""
When we store files by date,  just use the YEAR 2020 to store all files,  unless... we have more then REQUIRE_SUBFOLDERS
then add a subfolder with MONTH,  if the MONTH as more then REQUIRE_SBUFOLDERS,  add a day
"""

DF = TypeVar("DF", bound="Folder")  # pylint: disable=invalid-name


class ImageClean:  # pylint: disable=too-many-instance-attributes
    """
    This is the main class for image import,   create an instance,  and then .run it
    """
    def __init__(self, app, restore=False, **kwargs):
        self.app_name = app
        self.run_path = Path(Path.home().joinpath(f'.{self.app_name}'))
        if not self.run_path.exists():
            os.makedirs(self.run_path, mode=511)
        self.conf_file = self.run_path.joinpath('config.pickle')

        # Default option/values
        self.input_folder = self.output_folder = Path.home()
        self.verbose = False
        self.do_convert = True
        self.force_keep = False  # With R/O directories we can not ever try and remove anything
        self.keep_original_files = True
        self.check_for_small = False
        self.check_for_duplicates = False
        self.check_for_folders = True  # When set,  check for descriptive folder names, else just use dates.
        self.progress = 0

        if restore:  # Used by UI
            try:
                with open(self.conf_file, 'rb') as file:
                    temp = pickle.load(file)
                    self.process_args(temp)
            except FileNotFoundError:
                logger.debug('Restore attempt of %s failed', self.conf_file)
        else:  # Used by cmdline
            self.process_args(kwargs)

        self.duplicate_base = f'{self.app_name}_Duplicates'
        self.movies_base = f'{self.app_name}_ImageMovies'
        self.migration_base = f'{self.app_name}_Migrated'
        self.no_date_base = f'{self.app_name}_NoDate'
        self.small_base = f'{self.app_name}_Small'

        self.folders: Dict[str, DF] = {}  # This is used to store output folders - one to one map to folder object
        self.movie_list = []  # We need to track these so we can clean up
        self.working_folder = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with

    def process_args(self, kwargs: dict):
        """
        Allow for command line arguments
        :param kwargs:
        :return:
        """
        # pylint: disable=too-many-branches
        for key in kwargs:
            if key == 'verbose':
                self.verbose = kwargs[key]
            elif key == 'do_convert':
                self.do_convert = kwargs[key]
            elif key == 'input':
                self.input_folder = kwargs[key]
            elif key == 'output':
                self.output_folder = kwargs[key]
            elif key == 'keep_originals':
                self.keep_original_files = kwargs[key]
            elif key == 'check_duplicates':
                self.check_for_duplicates = kwargs[key]
            elif key == 'check_small':
                self.check_for_small = kwargs[key]
            elif key == 'check_description':
                self.check_for_folders = kwargs[key]
            else:  # pragma: no cover
                error_str = 'Argument:%s is being skipped failed', key
                logger.debug(error_str)
                assert False, error_str

    def save_config(self):  # pragma: no cover
        """
        Save,  for restarting
        :return:
        """
        config = {'verbose': self.verbose,
                  'do_convert': self.do_convert,
                  'input': self.input_folder,
                  'output': self.output_folder,
                  'keep_originals': self.keep_original_files,
                  'check_duplicates': self.check_for_duplicates,
                  'check_small': self.check_for_small,
                  'check_description': self.check_for_folders
                  }
        with open(self.conf_file, 'wb') as conf_file:
            pickle.dump(config, conf_file, pickle.HIGHEST_PROTOCOL)

    def print(self, text):
        """
        This is really only here so that I can override it in the GUI.
           cleaner_app.print = types.MethodType(self.progress.override_print, cleaner_app)

        :param text: something to display when verbose is true
        :return:  None
        """
        if self.verbose:
            print(text)

    def increment_progress(self):
        """
        Simple way to update progress / used in GUI
        :return:
        """
        self.progress += 1

    def setup(self):  # pylint: disable=invalid-name
        """
        For the GUI,  we need a way to 'prepare' the environment
        :return:
        """
        self.print(f'Preparing the environment: Input: {self.input_folder} Output: {self.output_folder}')

        assert os.access(self.output_folder, os.W_OK | os.X_OK)
        if not os.access(self.input_folder, os.W_OK | os.X_OK):
            self.force_keep = True

        # Register our internal folders
        Folder(self.output_folder, internal=True)
        Folder(self.output_folder.joinpath(self.no_date_base), internal=True)
        Folder(self.output_folder.joinpath(self.small_base), internal=True)
        Folder(self.output_folder.joinpath(self.migration_base), internal=True)
        Folder(self.output_folder.joinpath(self.duplicate_base), internal=True)
        Folder(self.output_folder.joinpath(self.movies_base), internal=True)

        logger.debug('Registration is Starting')
        self._register_files(self.output_folder)
        logger.debug('Registration is completed')

    def teardown(self):  # pylint: disable=invalid-name
        """
        Only logically way when you have prepared and run
        :return:
        """
        if self.working_folder:
            self.working_folder.cleanup()
            self.working_folder = None

    async def run(self):
        """
        This will call all the methods to do a run.    The GUI,  will need to do this as well
        """

        self.print('Registering existing images.')
        self.setup()
        # Start it up.
        self.print('Starting Imports.')
        await self.process_folder(self.input_folder)
        if self.check_for_duplicates:
            await self._process_duplicate_files()
        self.teardown()

        # Clean up
        self._process_duplicates_movies()
        self._balance_folders(self.output_folder, MAXIMUM_FOLDER_SIZE)
        self.print('Auditing folders.')
        self._audit_folders(self.output_folder)
        if self.output_folder != self.input_folder and not self.keep_original_files:
            self._audit_folders(self.input_folder)

    def _register_files(self, folder: Path, parent_folder: Folder = None):
        """
        Take an inventory of all the existing files/folders.  This allows us to easily detected duplicate files.
        :return:
        """
        this_folder = Folder.get_folder(folder)
        if not this_folder:
            this_folder = Folder(folder, cache=True)

        if parent_folder:
            parent_folder.children.append(this_folder)

        for entry in folder.iterdir():
            if entry.is_dir():
                try:
                    self._register_files(entry, this_folder)
                except PermissionError:
                    self.print(f'Warning output folder {entry} is not accessible')
            else:
                make_cleaner_object(entry).register()
                this_folder.count += 1

    def _folder_test(self, folder1, folder2) -> int:
        """
        compare two folders.   this is in the folderCleaner class but not much use for us with specialized folders
        :param folder1:
        :param folder2:
        :return:
        """
        # pylint: disable=too-many-return-statements
        if folder1 and folder2:
            # Need to filter out application specific descriptions
            folder1_description = None if folder1.description and folder1.description.startswith(
                self.app_name) else folder1.description
            folder2_description = None if folder2.description and folder2.description.startswith(
                self.app_name) else folder2.description

            if folder1_description and folder2_description:
                return EXACT
            if folder1_description and not folder2_description:
                return GREATER
            if folder2_description and not folder1_description:
                return LESSER  # pragma: no cover  Custom folder stuff again

            if folder1.date and folder2.date:
                if folder1.date > folder2.date:
                    return LESSER
                return GREATER
            if folder1.date and not folder2.date:
                return GREATER
            if folder2.date and not folder1.date:
                return LESSER
        return EXACT

    async def _process_duplicate_files(self):
        """
        Whenever we have multiple files with the same basic name,  we get multiple entries in the registry,  this
        will run an audit on them to make sure that they are still valid duplicates.

        :return:
        """
        self.print('Processing any duplicate files.')
        entries = deepcopy(CleanerBase.get_hash())  # This deepcopy is very slow!
        for entry in entries:
            if len(entries[entry]) > 1:

                for outer in range(len(entries[entry])):
                    this = entries[entry][outer]
                    if this:
                        # print(f'Potential Duplicate with Key {entry}')
                        if str(this.path).startswith(str(self.output_foler.joinpath(self.duplicate_base))):
                            continue  # This is already flagged as a duplicate
                        new_path = self.get_new_path(this)
                        if this.path.parent == new_path:  # I am still in the right place
                            for inner in range(outer + 1, len(entries[entry])):
                                value = entries[entry][inner]
                                if value and this == value:   # We are the same file with different locations weights
                                    folder_test = self._folder_test(this.folder, value.folder)
                                    if folder_test == GREATER:
                                        self.print(f'{value.path}: being treated as a duplicate')
                                        value.relocate_file(self.get_new_path(value, is_duplicate=True),
                                                            remove=self.remove_file(value))
                                        entries[entry][inner] = None
                                    elif folder_test == LESSER:
                                        self.print(f'{this.path}: being treated as a duplicate')
                                        this.relocate_file(self.get_new_path(this, is_duplicate=True),
                                                           remove=self.remove_file(this))
                                        break
                        else:  # I am not in the right place.
                            if new_path.joinpath(this.path.name).exists():
                                new_path = self.get_new_path(this, is_duplicate=True)
                            this.relocate_file(new_path, remove=self.remove_file(this))
        self.print('Duplicate processing completed')

    def _process_duplicates_movies(self):
        """
        While processing images,  we have both movies and images,  often due to iPhones we also have movie images.
        If I find a image and movie with the same name I am assuming they are they same.    So relocate or delete
        todo:   Make the logic stronger,  should they be in the same directory?   Should the movie be in no_date
        todo:   Maybe people what their damn clips in the same folder.   Make this an option.
        :return:
        """
        self.print('Processing any movie clips.')
        for entry in self.movie_list:
            for item in entry.get_registered():
                if item.path.suffix in PICTURE_FILES:
                    entry.de_register()
                    entry.relocate_file(self.output_folder.joinpath(self.movies_base),
                                        remove=True, rollover=False, register=False)
                    break

    '''def _balance_folders(self, root_path: Path, folder_size: int):
        """
        Using this root folder,  loop over each year folder (DDDD) and remove Day and Month folders if the count is
        below that of folder_size.

        Currently, we have too many Day folders with only one or two picture.   This makes the forest easier to see.

        :param root_path: where to find the  image files
        :return: None
        """

        dated_folders = Folder(root_path)
        for year in dated_folders.children:
            if year.total < folder_size:
                year.rollup_files(year.name)
            else:
                for month in year.children:
                    if month.total < folder_size:
                        month.rollup_files(month.name)'''

    def _audit_folders(self, path: Path):
        """
        Look for large and empty folders
        :param path:
        :return:
        """
        for entry in path.iterdir():
            if entry.is_dir():
                self._audit_folders(entry)
                size = len(os.listdir(entry))
                if size == 0:
                    self.print(f'  Removing empty folder {entry}')
                    os.rmdir(entry)
                elif size > WARNING_FOLDER_SIZE:
                    self.print(f'  VERY large folder ({size}) found {entry}')

    def get_new_path(self, path_obj: Union[FileCleaner, ImageCleaner], is_duplicate: bool = False) -> Optional[Path]:
        """
        Using the time stamp and current description build a folder path to where this file should be moved to.
        Requires self.duplicate_path,  self.small_path,   self.no_date_base

        base/<duplicate>/<small>/<nodate> | <year>/<description> | <year>/<month>/<day>

        :param: path_obj,  is the cleaner object we are trying to relocate
        :param: is_duplicate, this is a duplicate file so move it accordingly
        :return:  A Path representing where this file should be moved or None, if the base path was None
        """
        date = path_obj.date if path_obj.date else path_obj.folder.date if path_obj.folder else None
        description_path = self.get_descriptive_path(path_obj)

        base = self.output_folder
        base = base if not is_duplicate else self.output_folder.joinpath(self.duplicate_base)
        base = base if not (self.check_for_small and path_obj.is_small) else base.joinpath(self.small_base)
        base = base if date else base.joinpath(self.no_date_base)

        if date and description_path:
            return base.joinpath(str(path_obj.date.year)).joinpath(description_path)

        if not date and description_path:
            return base.joinpath(description_path)

        if date and not description_path:
            new = base.joinpath(str(path_obj.date.year)).joinpath(str(path_obj.date.month)).\
                joinpath(str(path_obj.date.day))
            if not new.exists():
                new = base.joinpath(str(path_obj.date.year)).joinpath(str(path_obj.date.month))
            if not new.exists():
                new = base.joinpath(str(path_obj.date.year))
            return new
        return base

    async def process_file(self, entry: Union[FileCleaner, ImageCleaner], folder: Folder):
        """
        Extract image date
        Calculate new destination folder
        Test Duplicate status

        param entry: Cleaner object, File or Image
        """

        self.increment_progress()
        await asyncio.sleep(0)  # Allow other sub-processes to interrupt us
        if not entry.is_valid:
            self.print(f'.... File {entry.path} is invalid.')
            return

        decorator = Path()
        if entry.path.suffix.lower() not in PICTURE_FILES:
            if entry.path.suffix.lower() in MOVIE_FILES:
                self.movie_list.append(entry.registry_key)
                decorator = Path(self.movies_base)
            else:
                self.print(f'.... Ignoring non image file {entry.path}')
                return

        if self.check_for_small and entry.is_small:
            decorator = self.small_base  # Assumption is that movies can not be small

        folder_base = entry.folder.build_base() if entry.folder else Path()
        if folder_base == Path():
            folder_base = entry.build_base()
        if folder_base == Path():
            folder_base = Path(self.no_date_base)

        if entry.folder and entry.folder.description and self.check_for_folders:
            folder_base = folder_base.joinpath(entry.folder.description)

        relo_path = self.output_folder.joinpath(decorator).joinpath(folder_base)
        if entry.path == relo_path:
            return  # Processing ourselves

        existing = entry.get_registered(new_path=relo_path)
        rollover = False
        if existing:
            if entry.test_for_duplicate(existing):
                relo_path = self.output_folder.joinpath(self.duplicate_base).joinpath(decorator).joinpath(folder_base)
            else:
                rollover = True
        entry.relocate_file(relo_path, register=True, rollover=rollover, remove=self.remove_file())

    async def process_folder(self, folder: Path):
        """
        Loop over the folders,  recursive
        :param folder:
        :return:
        """
        self.print(f'Processing Folder: {folder}')
        this_folder = Folder(folder, base_entry=self.input_folder, cache=False)

        for entry in folder.iterdir():
            if entry.is_dir():
                if Folder.is_internal(entry):
                    self.print(f'Skipping folder {entry}')
                else:
                    await self.process_folder(entry)
            elif entry.is_file():
                self.print(f'. File: {entry}')
                logger.debug('Processing File:%s', entry)
                await self.process_file(make_cleaner_object(entry), this_folder)

    def remove_file(self, obj: Union[FileCleaner, ImageCleaner]) -> bool:
        """
        Centralize the logic on whether we should remove or not
        :param obj:  A cleaner subclass
        :return: true if we should keep this
        """

        if str(obj.path).startswith(str(self.input_folder)):
            # This file is on the input path
            if self.force_keep:
                return False
            if self.keep_original_files:
                return False
        return True
