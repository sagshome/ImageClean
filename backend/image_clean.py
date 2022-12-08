"""
Run the actual image cleaning
"""
import asyncio
# pylint: disable=line-too-long

import logging
import os
import pickle
import sys
import tempfile

from copy import deepcopy
from pathlib import Path
from typing import Optional, Union

sys.path.append('.')
# pylint: disable=import-error wrong-import-position
from backend.cleaner import Cleaner, ImageCleaner, FileCleaner, FolderCleaner, file_cleaner, PICTURE_FILES, MOVIE_FILES

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


class ImageClean:  # pylint: disable=too-many-instance-attributes
    """
    This is the main class for image import,   create an instance,  and then .run it
    """
    def __init__(self, app: str, restore=False, **kwargs):
        self.app_name = app
        self.run_path = Path(Path.home().joinpath(f'.{self.app_name}'))
        if not self.run_path.exists():
            os.makedirs(self.run_path, mode=511, exist_ok=True)
        self.conf_file = self.run_path.joinpath('config.pickle')

        # Default option/values
        self.input_folder = Path.home()
        self.output_folder = Path.home()
        self.verbose = False
        self.do_convert = True
        self.force_keep = False  # With R/O directories we can not ever try and remove anything
        self.keep_original_files = True
        self.ignore_folders = []
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

        self.duplicate_path_base = f'{self.app_name}_Duplicates'
        self.image_movies_path_base = f'{self.app_name}_ImageMovies'
        self.migrated_path_base = f'{self.app_name}_Migrated'
        self.no_date_base = f'{self.app_name}_NoDate'
        self.small_base = f'{self.app_name}_Small'

        self.in_place = False
        self.no_date_path = None
        self.small_path = None
        self.migrated_path = None
        self.duplicate_path = None
        self.image_movies_path = None

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
            else:
                logger.debug('Argument:%s is being skipped failed', key)

    def save_config(self):
        """
        Save,  for restarting
        :return:
        """
        config = {'verbose': self.verbose,
                  'do_convert': self.do_convert,
                  'input': self.input_folder,
                  'output': self.output_folder,
                  'keep_originals': self.keep_original_files,
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

    def setUp(self):  # pylint: disable=invalid-name
        """
        For the GUI,  we need a way to 'prepare' the environment
        :return:
        """
        # pylint: disable=too-many-branches
        self.print(f'Preparing the environment: Input: {self.input_folder} Output: {self.output_folder}')
        if not self.output_folder.exists():
            os.mkdir(self.output_folder)

        assert os.access(self.output_folder, os.W_OK | os.X_OK)
        if not os.access(self.input_folder, os.W_OK | os.X_OK):
            self.force_keep = True  # pragma: win

        if self.output_folder == self.input_folder:
            self.in_place = True

        self.no_date_path = self.output_folder.joinpath(self.no_date_base)
        self.small_path = self.output_folder.joinpath(self.small_base)
        self.migrated_path = self.output_folder.joinpath(self.migrated_path_base)
        self.duplicate_path = self.output_folder.joinpath(self.duplicate_path_base)
        self.image_movies_path = self.output_folder.joinpath(self.image_movies_path_base)

        # Make sure we ignore these,  they came from us.
        self.ignore_folders.append(self.small_path)
        self.ignore_folders.append(self.migrated_path)
        self.ignore_folders.append(self.duplicate_path)
        self.ignore_folders.append(self.image_movies_path)

        if not self.no_date_path.exists():
            os.mkdir(self.no_date_path)
        if self.migrated_path and not self.migrated_path.exists():
            os.mkdir(self.migrated_path)
        if not self.duplicate_path.exists():
            os.mkdir(self.duplicate_path)
        if self.image_movies_path and not self.image_movies_path.exists():
            os.mkdir(self.image_movies_path)
        if self.small_path and not self.small_path.exists():
            os.mkdir(self.small_path)

        Cleaner.add_to_root_path(self.no_date_path)

        logger.debug('Registration is Starting')
        self._register_files(self.output_folder)
        logger.debug('Registration is completed')

    def tearDown(self):  # pylint: disable=invalid-name
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
        self.setUp()
        # Start it up.
        master = FolderCleaner(self.input_folder,
                               parent=None,
                               root_folder=self.input_folder,
                               output_folder=self.output_folder)
        master.description = None  # We need to do this to ensure that this folder name is not used a description
        self.print('Starting Imports.')
        await self.process_folder(master)
        await self._process_duplicate_files()
        self.tearDown()

        # Clean up
        master.reset()
        self._process_duplicates_movies()
        self.print('Auditing folders.')
        self._audit_folders(self.output_folder)

    def _register_files(self, output_dir: Path):
        """
        Take an inventory of all the existing files. This allows us to easily detected duplicate files.
        param output_dir where we will be moving file to
        :return:
        """
        for entry in output_dir.iterdir():
            if entry.is_dir():
                try:
                    self._register_files(entry)
                except PermissionError:  # pragma: no cover
                    pass  # This can happen,  just ignore it
            else:
                file_cleaner(entry, FolderCleaner(output_dir, app_name=self.app_name)).register(deep=False)

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
                return LESSER  # pragma: no cover

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
        # pylint: disable=too-many-nested-blocks
        self.print('Processing any duplicate files.')
        entries = deepcopy(Cleaner.get_hash())
        for entry in entries:
            if len(entries[entry]) > 1:
                for outer in range(len(entries[entry])):
                    this = entries[entry][outer]
                    if this:
                        self.print(f'Potential Duplicate with Key {entry}')
                        if str(this.path).startswith(str(self.duplicate_path)):  # pragma: no cover
                            continue  # This is already flagged as a duplicate
                        new_path = self.get_new_path(this)
                        if this.path.parent == new_path:  # I am still in the right place
                            for inner in range(outer + 1, len(entries[entry])):
                                value = entries[entry][inner]
                                if this == value:   # We are the same file with different locations weights
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
                                new_path = self.get_new_path(this, is_duplicate=True, preserve=True)
                            this.relocate_file(new_path, remove=self.remove_file(this))

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
            for item in entry.get_all_registered():
                if item.path.suffix in PICTURE_FILES:
                    entry.de_register()
                    entry.relocate_file(self.image_movies_path, remove=True, rollover=False, register=False)
                    break

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

    def get_new_path(self, path_obj: Cleaner, is_duplicate: bool = False, preserve: bool = False) -> Optional[Path]:
        """
        Using the time stamp and current location/description build a folder path to where this
        file should be moved to.
        :param: path_obj,  is the cleaner object we are trying to relocate
        :param: is_duplicate, this is a duplicate file so move it accordingly
        :param: preserve,  when a duplicate is processed you can optionally keep the old path even if it was wrong.
        :return:  A Path representing where this file should be moved or None, if the base path was None
        """
        # pylint: disable=too-many-branches
        base = self.output_folder
        if is_duplicate:
            base = self.duplicate_path
            if preserve:  # Used when processing duplicates, preserve the folder components
                for part in path_obj.path.parent.parts[len(self.output_folder.parts):]:
                    base = base.joinpath(part)
                return base

        if path_obj.is_small:
            base = self.small_path

        date = path_obj.date if path_obj.date else None
        description_path = None
        if path_obj.folder:
            description_path = path_obj.folder.recursive_description_lookup(None, [])
            if not date:
                date = path_obj.folder.date

        if not date and description_path:
            return base.joinpath(description_path)

        if not date:
            return base.joinpath(self.no_date_base)

        year = month = day = None
        if path_obj.date:
            year = path_obj.date.year
            month = path_obj.date.month
            day = path_obj.date.day

        new = base
        if year and description_path:
            new = base.joinpath(str(year)).joinpath(description_path)
        elif year:
            new = base.joinpath(str(year))
            if month:
                new = new.joinpath(str(month))
                if day:
                    new = new.joinpath(str(day))
        if not new.exists():
            os.makedirs(new)
        return new

    async def process_file(self, entry: Union[FileCleaner, ImageCleaner]):  # pylint: disable=too-many-branches
        """
        Perform any conversions
        Extract image date
        Calculate new destination folder
        Test Duplicate status

        param entry: Cleaner object, promoted to a subclass when processed
        """
        self.increment_progress()
        await asyncio.sleep(0)
        if not entry.is_valid:
            self.print(f'.... File {entry.path} is invalid.')
            return

        if self.do_convert:
            new = entry.convert(Path(self.working_folder.name), self.migrated_path, remove=self.remove_file(entry))
            if id(new) != id(entry):  # The file was converted and cleaned up
                entry = new  # pragma: win work on the converted file

        if entry.path.suffix.lower() not in PICTURE_FILES:
            if entry.path.suffix.lower() in MOVIE_FILES:
                self.movie_list.append(entry)
            else:
                self.print(f'.... Ignoring non image file {entry.path}')
                return

        new_path = self.get_new_path(entry)
        if not entry.is_registered():
            self.print(f'.. File: {entry.path} new file is relocating to {new_path}')
            entry.relocate_file(new_path, register=True, remove=self.remove_file(entry))
        else:
            found = False
            all_entries = deepcopy(entry.get_all_registered())  # save it, in case something new becomes registered
            for value in all_entries:
                if value == entry:  # File contents are identical
                    if value.path == entry.path:
                        found = True
                        if value.path.parent != new_path:
                            self.print(f'.. File: {entry.path} existing file is relocating to {new_path}')
                            entry.relocate_file(new_path, register=True, remove=True)
                        break
                    # These identical files are stored in different paths.
                    if value.path.parent == new_path:  # A copy already exists where we should be
                        found = True
                        duplicate_path = self.get_new_path(entry, is_duplicate=True)
                        if duplicate_path:
                            self.print(f'.. File: {entry.path} duplicate file relocating to {duplicate_path}')
                        entry.relocate_file(duplicate_path, remove=self.remove_file(entry))
                        break

            if not found:
                self.print(f'.. File: {entry.path} similar copy relocating to {new_path}')
                entry.relocate_file(new_path, register=True, remove=self.remove_file(entry))

    async def process_folder(self, folder: FolderCleaner):
        """
        Loop over the folders,  recursive
        :param folder:
        :return:
        """
        self.print(f'. Folder: {folder.path}')
        for entry in folder.path.iterdir():
            if entry.is_dir() and entry not in self.ignore_folders:  # Includes APP folders like ..._small
                this_folder = FolderCleaner(Path(entry), parent=folder, app_name=self.app_name)
                await self.process_folder(this_folder)
            elif entry.is_file():
                self.print(f'. File: {entry}')
                logger.debug('Processing File:%s', entry)
                await self.process_file(file_cleaner(entry, folder))

    def remove_file(self, obj: Union[FileCleaner, ImageCleaner]) -> bool:
        """
        Centralize the logic on whether we should remove or not
        :param obj:  A cleaner subclass
        :return: true if we should keep this
        """

        if str(obj.path).startswith(str(self.input_folder)):
            # This file is on the input path
            if self.force_keep:  # pragma: win
                return False
            if self.keep_original_files:
                return False
        return True
