"""
What about a name like philler  for photo filler
Run the actual image cleaning
09-2025 - Change of strategy.   Only valid base folders are:
    YYYY/<descriptions...></Movies | Small | <image_name_Similar (which should include image_name (A separate process))>
    YYYY/MM/<descriptions...></Movies | Small | <image_name_Similar (which should include image_name (A separate process))>
    NoDate/<descriptions...></Movies | Small | <image_name_Similar (which should include image_name (A separate process))>

    Using new imagehash to find actual duplicates,  same hash pick the largest file,  I should have more metadata
"""
import argparse
import asyncio

import logging
import os
import pickle
import sys
import tempfile
# import traceback

from pathlib import Path
from typing import List, Dict, TypeVar

from CleanerBase import CleanerBase, APPLICATION, config_dir, user_dir, PICTURE_FILES, MOVIE_FILES, IGNORE_FILES
from Folder import Folder
from StandardFile import StandardFile, FileCache
from ImageFile import ImageFile

logger = logging.getLogger(APPLICATION)  # pylint: disable=invalid-name

WARNING_FOLDER_SIZE = 100  # Used when auditing directories,  move then 100 members is a Yellow flag
MAXIMUM_FOLDER_SIZE = 50  # todo: Date based folder,  more than MAX,  create a child

DESCRIPTION = 'This application will reorganize image/data files into a folder structure that is human friendly'
EXTRA_HELP = 'Go to https://github.com/sagshome/ImageClean/wiki for details'

FULL_HELP = APPLICATION + """:
Organize images and data based on dates and folder names.  The date format is:"
* Level 1 - Year,  Level 2 - Month as in 2002/12 (December 5th, 2002)"
    Times are based off of 1) a existing directory with date values, 2) internal image time, 3) file time stamp"
* If the original folder had a name like 'Florida',  the new folder would be 2002/12/Florida"
    This structure should help you find your images much easier"

Import Images From' is where the images will be loaded from\n"
Save Images To' is where they will be stored - it can be the same as the From folder\n\n"
            "Options\n\n"
            "Keep Originals:        If selected no changes to Import From,  usually files are copied and deleted. \n"
            "Look for Thumbnails:   Isolate images that are very small (Often created by other importing software)\n"
            "Convert HEIC files:    Look for this format and if found convert to JPEG (HIEC are not displayed on Windows devices\n"
            "Preserve Folders:      On Image Import, check for descriptive folders. If not selected all files are store by date only\n"
"""


folders: dict[str: Folder] = {}


class CleanerApp:  # pylint: disable=too-many-instance-attributes
    """
    This is the main class for image import,   create an instance,  and then .run it
    used by both the cmdline and the GUI(s)
    """
    def __init__(self, **kwargs):
        """

        :param restore: bool - try and recover previous settings
        :param kwargs:
        """

        self.run_path = user_dir(APPLICATION)
        self.conf_file = config_dir(APPLICATION).joinpath('config.pickle')
        self.app_name = APPLICATION

        # Default option
        self.verbose: bool = False
        self.convert: bool = False                # If possible, change OSX/IOS heic images to jpeg
        self.remove: bool = False                 # Do not delete original photos
        self.small: bool = False                  # If a file is small,  append a 'Small' folder on output folders
        self.data: bool = False                   # Create a data folder under output_folder for non-image types
        self.match_date: bool = False             # When moving an image,  force the mtime, atime to match the image time (if it exists)
        self.fix_date: bool = False               # When importing,  force the image_time to match the file timestamp (will not overwrite image data if present)
        self.input_folder: Path | None = None
        self.output_folder: Path | None = None

        # Default values
        self.progress: int = 0
        self.force_keep: bool = False              # With R/O directories we can not ever try and remove anything
        if 'restore' in kwargs and kwargs['restore']:
            try:
                with open(self.conf_file, 'rb') as file:
                    temp = pickle.load(file)
                    self.process_args(temp)
            except FileNotFoundError:
                logger.error('Restore attempt of %s failed', self.conf_file)
                self.process_args(kwargs)
        else:  # Used by cmdline
            self.process_args(kwargs)

        self.movies_base: str = 'clips'
        self.migration_base: str = 'migrated'
        self.small_base: str = 'small'

        self.movie_list = []  # We need to track these so we can clean up
        self.working_folder = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with

        self.input_cache: FileCache = dict()
        self.output_cache: FileCache = dict()

    def process_args(self, kwargs: dict):
        """
        Allow for command line arguments
        :param kwargs:
        :return:
        """
        for key in kwargs:
            if key == 'verbose':
                self.verbose = kwargs[key]
            elif key == 'convert':
                self.convert = kwargs[key]
            elif key == 'input_folder':
                self.input_folder = Path(kwargs[key])
            elif key == 'output_folder':
                self.output_folder = Path(kwargs[key])
            elif key == 'remove':
                self.remove = kwargs[key]
            elif key == 'small':
                self.small = kwargs[key]
            elif key == 'data':
                self.data = kwargs[key]
            elif key == 'fix_date':
                self.fix_date = kwargs[key]
            elif key == 'match_date':
                self.match_date = kwargs[key]
            elif key == 'restore':
                pass  # This would be processed outside here
            else:  # pragma: no cover
                error_str = 'Argument:%s is being skipped failed', key
                logger.debug(error_str)

    def save_config(self):  # pragma: no cover
        """
        Save,  for restarting
        :return:
        """
        config = {'verbose': self.verbose,
                  'convert': self.convert,
                  'input_folder': self.input_folder,
                  'output_folder': self.output_folder,
                  'remove': self.remove,
                  'small': self.small,
                  'data': self.data,
                  'fix_date': self.fix_date,
                  'match_date': self.match_date,
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
        if self.verbose and text:
            print(text)

    def increment_progress(self):
        """
        Simple way to update progress / used in GUI
        :return:
        """
        self.progress += 1

    def setup(self) -> bool:
        """
        For the GUI,  we need a way to 'prepare' the environment
        :return:
        """
        self.print(f'Preparing the environment: Input Folder:{self.input_folder} Output Folder:{self.output_folder}')
        if not os.access(self.output_folder, os.W_OK | os.X_OK):
            try:
                os.makedirs(self.output_folder)
            except PermissionError:
                self.print(f'Fatal ERROR to create {self.output_folder}')
                return False

        if not os.access(self.input_folder, os.W_OK | os.X_OK):
            self.force_keep = True  # pragma: no cover

        logger.debug('Registration is Starting')
        self.register_files(self.output_folder, self.output_folder, self.output_cache, Folder(self.output_folder, base_entry=self.output_folder))
        self.register_files(self.input_folder, self.input_folder, self.input_cache, Folder(self.input_folder, base_entry=self.input_folder))
        logger.debug('Registration is completed')
        return True

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

        await self.import_from_cache()

        self.teardown()

    def register_files(self, folder: Path, base: Path, cache: FileCache, parent_folder: Folder = None):
        """
        Take an inventory of all the existing files/folders.  This allows us to easily detected duplicate files.
        :return:
        """
        for entry in folder.iterdir():
            if entry.is_dir():
                self.register_files(entry, base, cache, parent_folder)
            elif entry.is_file:
                this_folder = entry.parent.as_posix()
                if this_folder not in folders:
                    folders[this_folder] = Folder(entry.parent, base_entry=base)
                parent_folder = folders[this_folder]
                if CleanerBase.is_image(entry):
                    ImageFile(entry, parent_folder).cache(cache)
                else:
                    StandardFile(entry, parent_folder).cache(cache)

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

    def import_set(self) -> (List[StandardFile], List[StandardFile]):
        """
        Using the input cache,   find the best choices of input files based on the normalized name.
        Based on that list, compare the values to what we already have in the output cache,  if the files does not exist, or the folder stucture on the
           input is better. then add it to the output List
        :return: A list of FileObjects to Import and a List of FileObject to Skip (for reporting)
        """
        results: List[StandardFile] = []
        excludes: List[StandardFile] = []
        self.print('Calculating files that need to be processed')
        for normalized_name in self.input_cache:                                                  # Over each file in the input_cache
            elements: List[StandardFile] = []                                                     # Work with a smaller temporary array
            for full_name in self.input_cache[normalized_name]:                                   # check every file regardless of filename
                for to_test in self.input_cache[normalized_name][full_name]:                      # Over each file instance with a name of filename
                    if to_test not in elements:                                                   # See if we already have this file
                        elements.append(to_test)                                                  # and add it if we don't
                    else:
                        match = elements.index(to_test)                                           # find the previous instance of this exact file
                        if to_test < elements[match]:                                             # This version is no better
                            excludes.append(to_test)                                              # So exclude it
                        else:
                            excludes.append(elements[match])                                      # This version is better so exclude the previous version
                            elements.remove(elements[match])                                      # and remove it from the 'good' ones
                            elements.append(to_test)                                              # Add the new one

            for element in elements:                                                              # Elements are now just the best of the file with this name
                existing = element.get_cache_best(self.output_cache)                                    # See if this file already exists on the output folder
                if not existing or  element > existing:                                           # if it doesn't or this one is better
                    results.append(element)                                                       # then save it
                else:
                    excludes.append(element)                                                      # This is no better than what we had, so we will exclude it

        return results, excludes

    async def import_from_cache(self):
        entry: StandardFile | ImageFile
        to_move, to_skip = self.import_set()
        self.print(f'Starting import process - {len(to_move)} files to process')
        for entry in to_move:
            self.print(f'Starting import process - {entry.path} files to process')
            self.increment_progress()
            await asyncio.sleep(0)  # Allow other sub-processes to interrupt us
            if not entry.is_valid:
                self.print(f'.... File {entry.path} is invalid.')
                return

            suffix = entry.path.suffix.lower()
            if suffix in IGNORE_FILES:
                self.print(f'.... File {entry.path} is being ignored - {entry.path.suffix} file types are ignored.')
                return

            if self.convert:
                entry = entry.convert(Path(self.working_folder.name), self.output_folder, output_cache=self.output_cache, keep=self.keep_file(entry))

            new_path = entry.destination_path()
            if suffix in MOVIE_FILES:
                new_path = new_path.joinpath('clips')         # Keep all the movie clips together (respecting descriptions)
            elif self.data and suffix not in PICTURE_FILES:
                new_path = Path('data').joinpath(new_path)    # Keep all the data together (separate from images/movies)
            elif self.small and entry.is_small:
                new_path = new_path.joinpath('small')         # Keep all the small files together (respecting descriptions)

            new_path = self.output_folder.joinpath(new_path)  # Preface, the path with the output folder value

            self.print(entry.relocate_file(new_path.joinpath(entry.refactored_name), cache=self.output_cache,
                                           keep=self.keep_file(entry), fix_date=self.fix_date, match_date=self.match_date))

    @classmethod
    def audit_from_cache(cls, cache):
        for element in cache['by_name']:
            for size in cache['by_name'][element]:
                all_elements = []
                best = None
                for name in cache['by_name'][element][size]:
                    for file in cache['by_name'][element][size][name]:
                        if not best:
                            best = cache['by_name'][element][size][name][0]
                        else:
                            if file > best:
                                best = file
                        all_elements.append(file)
                all_elements.remove(best)

    def keep_file(self, obj: StandardFile = None) -> bool:
        """
        Centralize the logic on whether we should remove or not
        :param obj:  A cleaner subclass
        :return: true if we should keep this
        """
        if str(obj.path).startswith(str(self.input_folder)):
            # This file is on the input path
            if self.force_keep:
                return True
            if not self.remove:
                return True
        return False
