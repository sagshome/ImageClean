import logging
import os
import pickle
import platform
import re

import piexif

from datetime import datetime
from filecmp import cmp
from functools import cached_property
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from shutil import copyfile
from typing import List, Dict, Optional, TypeVar, Union

from Backend.Cleaner import ImageCleaner, FileCleaner, FolderCleaner, file_cleaner, \
    NEW_FILE, EXACT_FILE, LESSER_FILE, GREATER_FILE, SMALL_FILE, WARNING_FOLDER_SIZE


logger = logging.getLogger('Cleaner')


class ImageClean:

    def __init__(self, app: str, restore=False, **kwargs):
        self.app_name = app
        self.run_path = Path(Path.home().joinpath(f'.{self.app_name}'))
        if not self.run_path.exists():
            os.makedirs(self.run_path, mode=511, exist_ok=True)
        self.conf_file = self.run_path.joinpath('config.pickle')

        # Default option/values
        self.input_folder = Path.home()
        self.output_folder = Path.home()
        self.verbose = True
        self.do_convert = True  # todo: Provide an option for this
        self.recreate = False
        self.force_keep = False  # With R/O directories we can not ever try and remove anything
        self.keep_duplicates = False
        self.keep_movie_clips = False
        self.process_all_files = False  # todo: re-evaluate this
        self.keep_converted_files = False
        self.keep_original_files = True
        self.ignore_folders = []
        self.bad_parents = []
        self.progress = 0

        if restore:  # Used by UI
            try:
                f = open(self.conf_file, 'rb')
                temp = pickle.load(f)
                self.process_args(temp)
            except FileNotFoundError:
                pass
        else:  # Used by cmdline
            self.process_args(kwargs)

        self.duplicate_path_base = f'{self.app_name}_Duplicates'
        self.movie_path_base = f'{self.app_name}_ImageMovies'
        self.converted_path_base = f'{self.app_name}_Migrated'
        self.no_date_base = f'{self.app_name}_NoDate'
        self.small_base = f'{self.app_name}_Small'

        self.in_place = False
        self.no_date_path = None
        self.small_path = None
        self.migrated_path = None
        self.duplicate_path = None
        self.image_movies_path = None

    def process_args(self, kwargs: dict):
        for key in kwargs:
            if key == 'verbose':
                self.verbose = kwargs[key]
            elif key == 'recreate':
                self.recreate = kwargs[key]
            elif key == 'do_convert':
                self.do_convert = kwargs[key]
            elif key == 'input':
                self.input_folder = kwargs[key]
            elif key == 'output':
                self.output_folder = kwargs[key]
            elif key == 'keep_duplicates':
                self.keep_duplicates = kwargs[key]
            elif key == 'keep_clips':
                self.keep_movie_clips = kwargs[key]
            elif key == 'keep_conversions':
                self.keep_converted_files = kwargs[key]
            elif key == 'keep_originals':
                self.keep_original_files = kwargs[key]
            elif key == 'ignore_folders':
                for value in kwargs[key]:
                    self.ignore_folders.append(value)
            elif key == 'bad_parents':
                for value in kwargs[key]:
                    self.bad_parents.append(value)
            else:
                assert False, f'Invalid option supplied: {key}'

    def save_config(self):
        config = {'verbose': self.verbose,
                  'recreate': self.recreate,
                  'do_convert': self.do_convert,
                  'input': self.input_folder,
                  'output': self.output_folder,
                  'keep_duplicates': self.keep_duplicates,
                  'keep_clips': self.keep_movie_clips,
                  'keep_conversions': self.keep_converted_files,
                  'keep_originals': self.keep_original_files,
                  'ignore_folders': self.ignore_folders,
                  'bad_parents': self.bad_parents,
                  }
        with open(self.conf_file, 'wb') as f:
            pickle.dump(config, f, pickle.HIGHEST_PROTOCOL)

    def print(self, text):
        if self.verbose:
            print(text)

    def increment_progress(self):
        self.progress += 1

    def set_recreate(self, value: bool):
        self.recreate = value

    def set_keep_duplicates(self, value: bool):
        self.keep_duplicates = value

    def set_keep_movie_clips(self, value: bool):
        self.keep_movie_clips = value

    def set_keep_converted_files(self, value: bool):
        self.keep_converted_files = value

    def set_keep_original_files(self, value: bool):
        self.keep_original_files = value

    def add_ignore_folder(self, value: Path):
        if value not in self.ignore_folders:
            self.ignore_folders.append(value)
            return True
        return False

    def add_bad_parents(self, value: Path):
        if value not in self.bad_parents:
            self.bad_parents.append(value)
            return True
        return False

    def set_paranoid(self, value: bool):
        self.set_keep_duplicates(value)
        self.set_keep_original_files(value)
        self.set_keep_converted_files(value)
        self.set_keep_movie_clips(value)
        self.force_keep = value

    def prepare(self):
        """
        Some further processing once all the options have been set.
        """

        assert os.access(self.output_folder, os.W_OK | os.X_OK)
        self.force_keep = os.access(self.input_folder, os.W_OK | os.X_OK) | self.force_keep  # in case we are paranoid

        if self.output_folder == self.input_folder:
            if self.recreate:
                assert False, f'Can not recreate with same input/output folders: {self.input_folder}\n\n'
            self.in_place = True
            self.force_keep = False  # This just makes no sense - even IF paranoid, the point is to move files !

        # Make sure we ignore these,  they came from us.
        self.ignore_folders.append(self.output_folder.joinpath(self.movie_path_base))
        self.ignore_folders.append(self.output_folder.joinpath(self.duplicate_path_base))
        self.ignore_folders.append(self.output_folder.joinpath(self.converted_path_base))
        self.ignore_folders.append(self.output_folder.joinpath(self.small_base))

        self.bad_parents.append(self.no_date_base)
        self.bad_parents.append(self.movie_path_base)
        self.bad_parents.append(self.duplicate_path_base)
        self.bad_parents.append(self.converted_path_base)
        self.bad_parents.append(self.small_base)

        self.no_date_path = self.output_folder.joinpath(self.no_date_base)
        self.small_path = self.output_folder.joinpath(self.small_base)

        if self.keep_converted_files:
            self.migrated_path = self.output_folder.joinpath(self.converted_path_base)

        if self.keep_duplicates:
            self.duplicate_path = self.output_folder.joinpath(self.duplicate_path_base)

        if self.keep_movie_clips:
            self.image_movies_path = self.output_folder.joinpath(self.movie_path_base)

        # Backup any previous attempts

        if not self.recreate or self.in_place:  # Same root or importing from a new location
            self.register_files(self.output_folder)

        if self.recreate:
            if self.output_folder.exists():
                os.rename(self.output_folder, f'{self.output_folder}_{datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}')

        os.mkdir(self.output_folder) if not self.output_folder.exists() else None
        os.mkdir(self.no_date_path) if not self.no_date_path.exists() else None
        os.mkdir(self.migrated_path) if self.migrated_path and not self.migrated_path.exists() else None
        os.mkdir(self.duplicate_path) if self.duplicate_path and not self.duplicate_path.exists() else None
        os.mkdir(self.image_movies_path) if self.image_movies_path and not self.image_movies_path.exists() else None
        os.mkdir(self.small_path) if self.small_path and not self.small_path.exists() else None

    def register_files(self, output_dir: Path):
        """
        Take an inventory of all the existing files.    This allows us to easily detected duplicate files.
        :param output_dir:  where we will be moving file to
        :return:
        """
        for entry in output_dir.iterdir():
            if entry.is_dir():
                self.register_files(entry)
            else:
                #if not entry.parent == output_dir:  # The base of the output directory should not contain files,  if
                                                    # it does they were not added by us so they need to be pr
                file_cleaner(entry, FolderCleaner(output_dir)).register()

    @staticmethod
    def duplicate_get(entry: Union[ImageCleaner, FileCleaner]) -> Optional[Union[ImageCleaner, FileCleaner]]:
        matched = None
        for value in entry.get_all_registered():
            if entry == value:
                if entry.path == value.path:  # The image data is exactly the same
                    return value
                else:
                    matched = value
        logger.error(f'Expecting to find a duplicate for {entry.path}')
        return matched

    @staticmethod
    def duplicates_test(entry: Union[ImageCleaner, FileCleaner]) -> int:
        """
        Test for duplicates, based on registered files
        :param entry: The instance of the current file
        :return: int,
        """

        result = NEW_FILE
        if entry.is_small:
            result = SMALL_FILE
        elif not entry.is_registered():
            result = NEW_FILE  # This is a new FileCleaner instance.
        else:
            for value in entry.get_all_registered():
                if entry == value:  # The data is exactly the same
                    if entry.folder == value.folder:  # Folders have same weight
                        if entry < value:
                            return LESSER_FILE
                        elif entry > value:
                            return GREATER_FILE
                    elif entry.folder > value.folder:
                        return GREATER_FILE
                    elif entry.folder < value.folder:
                        return LESSER_FILE

                    # Lets use the file date
                    if entry.date == value.date:
                        if entry.folder.date == value.folder.date:
                            return EXACT_FILE
                        elif entry.folder.date and value.folder.date:
                            if entry.folder.date < value.folder.date:
                                return GREATER_FILE
                            elif entry.folder.date > value.folder.date:
                                return LESSER_FILE
                        if entry.folder.date and not value.folder.date:
                            return GREATER_FILE
                        if not entry.folder.date and value.folder.date:
                            return LESSER_FILE
                    elif entry.date < value.date:
                        return GREATER_FILE
                    else:
                        return LESSER_FILE
                    return EXACT_FILE
        return result

    def process_duplicates_movies(self, movie_dir):
        for entry in movie_dir.path.iterdir():
            if entry.is_dir():
                self.process_duplicates_movies(FolderCleaner(Path(entry), movie_dir.root_folder, parent=movie_dir))
            elif entry.is_file():
                file_entry = FileCleaner(Path(entry), folder=movie_dir)
                if file_entry.path.suffix in file_entry.all_movies:
                    # todo: Use .stem property ...
                    just_name = file_entry.path.stem
                    for suffix in file_entry.all_images:
                        if FileCleaner(Path(f'{just_name}{suffix}')).is_registered():
                            if self.image_movies_path:
                                self.print(f'.... Saving Clip {file_entry.path}')
                                file_entry.relocate_file(self.image_movies_path, remove=True)
                            else:
                                self.print(f'.... Removing Clip {file_entry.path}')
                                os.unlink(file_entry.path)
                            break

    def audit_folders(self, path: Path) -> List[Path]:
        large_folders = []
        for entry in path.iterdir():
            if entry.is_dir():
                self.audit_folders(entry)
                size = len(os.listdir(entry))
                if size == 0:
                    self.print(f'  Removing empty folder {entry}')
                    os.rmdir(entry)
                elif size > WARNING_FOLDER_SIZE:
                    large_folders.append(entry)
                    self.print(f'  VERY large folder ({size}) found {entry}')
        return large_folders

    def process_file(self, entry: Union[FileCleaner, ImageCleaner]):
        """
        Perform any conversions
        Extract image date
        Calculate new destination folder
        Test Duplicate status

        :param entry: Cleaner object,  promoted to a subclass when processed
        """
        self.print(f'.. File: {entry.path}')
        self.increment_progress()

        if not entry.is_valid:
            self.print(f'.... File {entry.path} is invalid.')
            return

        new_entry = entry.convert(self.migrated_path, self.run_path, in_place=self.in_place)
        if id(new_entry) != id(entry):  # The file was converted and cleaned up
            entry = new_entry  # work on the converted file

        if not self.process_all_files:
            if entry.path.suffix not in entry.all_images:
                if entry.path.suffix not in entry.all_movies:
                    self.print(f'.... Ignoring non image file {entry.path}')
                    return

        # Now lets go about building our output folder
        if entry.date:
            new_path = entry.get_new_path(self.output_folder, invalid_parents=self.bad_parents)
        else:  # make sure we do not over process things already determined to not be 'no date' files.
            if str(entry.path.parent).startswith(str(self.no_date_path)):
                new_path = entry.path.parent
            else:
                new_path = entry.get_new_path(self.no_date_path)

        dup_result = self.duplicates_test(entry)
        logger.debug(f'Duplicate Test: {dup_result} - {entry.path}')
        if dup_result == NEW_FILE:  # We have not seen this file before
            entry.relocate_file(new_path, register=True,  rollover=True,
                                remove=not self.keep_original_files or self.in_place or not self.force_keep)
        elif dup_result == SMALL_FILE:  # This file was built by some post processor (apple/windows) importer
            entry.relocate_file(entry.get_new_path(self.small_path), rollover=False,
                                remove=not self.keep_original_files or not self.force_keep)
        elif dup_result in (GREATER_FILE, LESSER_FILE, EXACT_FILE):
            existing = self.duplicate_get(entry)
            if not entry.path == existing.path:  # We are the same file,  do nothing
                if dup_result in (LESSER_FILE, EXACT_FILE):
                    entry.relocate_file(entry.get_new_path(self.duplicate_path), create_dir=False, rollover=False,
                                        remove=not self.keep_original_files or self.in_place or not self.force_keep)
                elif dup_result == GREATER_FILE:
                    existing.relocate_file(existing.get_new_path(self.duplicate_path),
                                           remove=not self.keep_original_files or not self.force_keep,
                                           create_dir=False, rollover=False)
                    entry.relocate_file(new_path, register=True, remove=self.in_place or not self.force_keep,
                                        rollover=False)
        else:
            assert False, f'Invalid test result {dup_result}'

    def process_folder(self, folder: FolderCleaner):
        self.print(f'. Folder: {folder.path}')
        for entry in folder.path.iterdir():
            if entry.is_dir() and entry not in self.ignore_folders:
                this_folder = FolderCleaner(Path(entry), parent=folder)
                if this_folder.description in self.bad_parents:
                    this_folder.description = None
                self.process_folder(this_folder)
            elif entry.is_file():
                self.process_file(file_cleaner(entry, folder))
            else:
                self.print(f'. Folder: {entry} ignored ')
        folder.clean_working_dir(self.run_path)  # Cleans up any temporary files that have been made
