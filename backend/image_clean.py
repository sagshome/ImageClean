"""
Run the actual image cleaning
"""
import asyncio

import logging
import os
import pickle
import sys
import tempfile
# import traceback

from pathlib import Path
from typing import Union, Dict, TypeVar

sys.path.append('.')
# pylint: disable=import-error wrong-import-position
from backend.cleaner import ImageCleaner, FileCleaner, Folder, make_cleaner_object, PICTURE_FILES, MOVIE_FILES

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

        # Default option
        self.verbose = False
        self.do_convert = False
        self.keep_original_files = True
        self.check_for_small = False
        self.check_for_folders = True  # When set,  check for descriptive folder names, else just use dates.

        # Default values
        self.input_folder = self.output_folder = Path.home()
        self.progress = 0
        self.force_keep = False  # With R/O directories we can not ever try and remove anything

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
            elif key == 'check_small':
                self.check_for_small = kwargs[key]
            # elif key == 'check_description':
            #    self.check_for_folders = kwargs[key]
            else:  # pragma: no cover
                error_str = 'Argument:%s is being skipped failed', key
                logger.debug(error_str)
                # assert False, error_str

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

    def setup(self):
        """
        For the GUI,  we need a way to 'prepare' the environment
        :return:
        """
        self.print(f'Preparing the environment: Input: {self.input_folder} Output: {self.output_folder}')

        assert os.access(self.output_folder, os.W_OK | os.X_OK)
        if not os.access(self.input_folder, os.W_OK | os.X_OK):
            self.force_keep = True

        # Register our internal folders
        Folder(self.output_folder, self.output_folder, internal=True)
        Folder(self.output_folder.joinpath(self.no_date_base), self.output_folder, internal=True)
        Folder(self.output_folder.joinpath(self.small_base), self.output_folder, internal=True)
        Folder(self.output_folder.joinpath(self.migration_base), self.output_folder, internal=True)
        Folder(self.output_folder.joinpath(self.duplicate_base), self.output_folder, internal=True)
        Folder(self.output_folder.joinpath(self.movies_base), self.output_folder, internal=True)

        logger.debug('Registration is Starting')
        self._register_files(self.output_folder)
        logger.debug('Registration is completed')

    def teardown(self):
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

        self.setup()
        # Start it up.
        self.print('Starting Imports.')
        await self.import_folder(self.input_folder)
        self.teardown()

        # Clean up

        self.print('Auditing folders.')
        try:
            self.input_folder.relative_to(self.output_folder)
        except ValueError:  # ValueError is caused by relative_to,  no common path so
            self._audit_folders(self.input_folder)
        self._audit_folders(self.output_folder)

    def _register_files(self, folder: Path, parent_folder: Folder = None):
        """
        Take an inventory of all the existing files/folders.  This allows us to easily detected duplicate files.
        :return:
        """
        this_folder = Folder.get_folder(folder)
        if not this_folder:
            this_folder = Folder(folder, self.output_folder, cache=True)

        if parent_folder:
            parent_folder.children.append(this_folder)

        for entry in folder.iterdir():
            if entry.is_dir():
                self._register_files(entry, this_folder)
            else:
                make_cleaner_object(entry).register()

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

    async def import_file(self, entry: Union[FileCleaner, ImageCleaner], folder: Folder):
        """
        Extract image date
        Calculate new destination folder
        Test Duplicate status

        param entry: Cleaner object, File or Image
        """

        # if entry.path.name == '151-5181_IMG.JPG':
        #    pass

        self.increment_progress()
        await asyncio.sleep(0)  # Allow other sub-processes to interrupt us
        if not entry.is_valid:
            self.print(f'.... File {entry.path} is invalid.')
            return

        decorator = Path()
        suffix = entry.path.suffix.lower()
        if suffix not in PICTURE_FILES:
            if suffix in MOVIE_FILES:
                self.movie_list.append(entry.registry_key)
                decorator = Path(self.movies_base)
            else:
                self.print(f'.... Ignoring non image file {entry.path}')
                return

        if self.check_for_small and entry.is_small:
            decorator = self.small_base  # Assumption is that movies can not be small

        # Folder base is calculated to be the proper location for this entry
        folder_base = entry.folder_base2(input_folder=folder, no_date_base=Path(self.no_date_base))
        relo_path = self.output_folder.joinpath(decorator).joinpath(folder_base)

        rollover = False

        # We have entry.path,  relo_path,  existing.path
        if entry.is_registered(by_file=True, by_path=True) and entry.path.parent == relo_path:
            return  # This is in fact me.
        logger.debug('  Importing File:%s', entry)
        if entry.is_registered(by_file=True, new_path=relo_path):  # This is a copy of me,  I am a duplicate
            dup_folder = self.output_folder.joinpath(self.duplicate_base).joinpath(decorator).joinpath(folder_base)
            entry.relocate_file(dup_folder, register=False, rollover=False, remove=self.remove_file(entry))
            return
        if entry.is_registered(by_file=True):  # A copy of me lives elsewhere.    Let's examine it
            for existing in entry.get_registered(by_file=True):
                if (not existing.folder) or (existing.folder and (not existing.folder.description)):
                    if existing.path.stat().st_ino != entry.path.stat().st_ino:  # Prevent moving myself to duplicate
                        base = existing.folder_base2(no_date_base=Path(self.no_date_base))
                        dup_folder = self.output_folder.joinpath(self.duplicate_base).joinpath(decorator).joinpath(base)
                        existing.de_register()
                        existing.relocate_file(dup_folder, register=False, rollover=False, remove=True)
                # else this copy is in descriptive folder so leave it be.
        elif entry.is_registered(new_path=relo_path):  # This is the same path, different file
            rollover = True
        # else, i new or a file with the same base name living elsewhere
        entry.relocate_file(relo_path, base_folder=self.output_folder, register=True, rollover=rollover,
                            remove=self.remove_file(entry))

    async def import_folder(self, folder: Path):
        """
        Provided with a folder to import,  recursively process this moving files to output
        :param folder:
        :return:
        """
        self.print(f'Scanning Folder: {folder}')
        this_folder = Folder(folder, self.input_folder, cache=False)
        if folder == self.output_folder.joinpath(self.no_date_base):
            this_folder.description = ''  # This is a special case where we are reimporting ourselves

        for entry in folder.iterdir():
            if entry.is_dir():
                if Folder.is_internal(entry) and (not entry == self.input_folder.joinpath(self.no_date_base)):
                    self.print(f'Skipping folder {entry}')  # We always process no_date_base
                else:
                    await self.import_folder(entry)
            else:
                self.print(f'. File: {entry}')
                await self.import_file(make_cleaner_object(entry), this_folder)

    def remove_file(self, obj: Union[FileCleaner, ImageCleaner] = None) -> bool:
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
