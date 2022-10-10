import logging
import os
import pickle
import tempfile


from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

from Backend.Cleaner import Cleaner, ImageCleaner, FileCleaner, FolderCleaner, file_cleaner


logger = logging.getLogger('Cleaner')

NEW_FILE: int = 0
EXACT_FILE: int = 1
LESSER_FILE: int = 2
GREATER_FILE: int = 3
SMALL_FILE: int = 4

WARNING_FOLDER_SIZE = 100  # Used when auditing directories,  move then 100 members is a Yellow flag


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
                f.close()
            except FileNotFoundError:
                logger.debug(f'Restore attempt of {self.conf_file} failed')
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
        self.suspicious_folders = []
        self.working_folder = tempfile.TemporaryDirectory()

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
                assert False, f'Invalid option supplied: {key}'  # pragma: no cover

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
        """
        This is really only here so that I can override it in the GUI.
           cleaner_app.print = types.MethodType(self.progress.override_print, cleaner_app)

        :param text: something to display when verbose is true
        :return:  None
        """
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

    def add_bad_parents(self, value: str):
        if value not in self.bad_parents:
            self.bad_parents.append(value)
            return True
        return False

    def set_paranoid(self, value: bool):
        self.set_keep_duplicates(value)
        self.set_keep_original_files(value)
        self.set_keep_converted_files(value)
        self.set_keep_movie_clips(value)

    def prepare(self):
        assert os.access(self.output_folder, os.W_OK | os.X_OK)
        if not os.access(self.input_folder, os.W_OK | os.X_OK):
            self.force_keep = True

        if self.output_folder == self.input_folder:
            if self.recreate:
                assert False, f'Can not recreate with same input/output folders: {self.input_folder}\n\n'
            self.in_place = True

        # Make sure we ignore these,  they came from us.
        self.ignore_folders.append(self.output_folder.joinpath(self.image_movies_path_base))
        self.ignore_folders.append(self.output_folder.joinpath(self.duplicate_path_base))
        self.ignore_folders.append(self.output_folder.joinpath(self.migrated_path_base))
        self.ignore_folders.append(self.output_folder.joinpath(self.small_base))

        self.bad_parents.append(self.no_date_base)
        self.bad_parents.append(self.image_movies_path_base)
        self.bad_parents.append(self.duplicate_path_base)
        self.bad_parents.append(self.migrated_path_base)
        self.bad_parents.append(self.small_base)

        self.no_date_path = self.output_folder.joinpath(self.no_date_base)
        self.small_path = self.output_folder.joinpath(self.small_base)

        if self.keep_converted_files:
            self.migrated_path = self.output_folder.joinpath(self.migrated_path_base)

        if self.keep_duplicates:
            self.duplicate_path = self.output_folder.joinpath(self.duplicate_path_base)

        if self.keep_movie_clips:
            self.image_movies_path = self.output_folder.joinpath(self.image_movies_path_base)

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

        Cleaner.add_to_root_path(self.no_date_path)

    def stop(self):
        if self.working_folder:
            self.working_folder.cleanup()
            self.working_folder = None

    def run(self):
        """
        Some further processing once all the options have been set.
        """
        self.prepare()
        # Start it up.
        master = FolderCleaner(self.input_folder,
                               parent=None,
                               root_folder=self.input_folder,
                               output_folder=self.output_folder)
        master.description = None  # We need to do this to ensure that this folder name is not used a description
        self.process_folder(master)

        self.stop()

        # Clean up
        master.reset()
        self.process_duplicates_movies()
        self.audit_folders(self.output_folder)

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
                file_cleaner(entry, FolderCleaner(output_dir, app_name=self.app_name)).register()

    @staticmethod
    def duplicate_get(entry: Union[ImageCleaner, FileCleaner]) -> Optional[Union[ImageCleaner, FileCleaner]]:
        matched = None
        for value in entry.get_all_registered():
            if entry == value:
                if entry.path == value.path:  # The image data is exactly the same
                    return value
                else:
                    matched = value
        if not matched:
            logger.error(f'Expecting to find a duplicate for {entry.path}')  # pragma: no cover
        return matched

    @staticmethod
    def duplicates_test(entry: Union[ImageCleaner, FileCleaner]) -> int:
        """
        Test for duplicates, based on registered files
        :param entry: The instance of the current file
        :return: int,

        Custom folders are always choice one
        File Dates are choice two
        Folder Dates are choice 3
             for images identical files pick the earlier one
        """

        result = NEW_FILE
        if entry.is_small:
            result = SMALL_FILE
        elif not entry.is_registered():
            result = NEW_FILE  # This is a new FileCleaner instance.
        else:  # work to do.
            for value in entry.get_all_registered():   # todo: Not processing multiple instances! all custom ???
                if entry == value:  # The data is exactly the same - data does not include dates
                    if entry.folder != value.folder:  # Folders don't same weight  - choice 1
                        if entry.folder > value.folder:
                            return GREATER_FILE
                        else:
                            return LESSER_FILE
                    else:
                        if entry < value:
                            return LESSER_FILE if entry.__class__.__name__ == 'ImageCleaner' else GREATER_FILE
                        elif entry > value:
                            return GREATER_FILE if entry.__class__.__name__ == 'ImageCleaner' else LESSER_FILE
                        else:
                            if entry.folder.date == value.folder.date:
                                return EXACT_FILE
                            elif entry.folder.date and value.folder.date:
                                if entry.folder.date < value.folder.date:
                                    return GREATER_FILE
                                elif entry.folder.date > value.folder.date:
                                    return LESSER_FILE
        return result

    def process_duplicates_movies(self):
        """
        While processing images,  we have both movies and images,  often due to iPhones we also have movie images.
        If I find a image and movie with the same name I am assuming they are they same.    So relocate or delete
        todo:   Make the logic stronger,  should they be in the same directory?   Should the movie be in no_date
        todo:   Maybe people what their damn clips in the same folder.   Make this an option.
        :return:
        """
        for entry in self.movie_list:
            for item in entry.get_all_registered():
                if item.path.suffix in item.all_images:
                    entry.de_register()
                    if self.keep_movie_clips:
                        entry.relocate_file(self.image_movies_path, remove=True, rollover=False, register=False)
                    else:
                        entry.path.unlink()
                    break

    def audit_folders(self, path: Path):
        for entry in path.iterdir():
            if entry.is_dir():
                self.audit_folders(entry)
                size = len(os.listdir(entry))
                if size == 0:
                    self.print(f'  Removing empty folder {entry}')
                    os.rmdir(entry)
                elif size > WARNING_FOLDER_SIZE:
                    self.suspicious_folders.append(entry)
                    self.print(f'  VERY large folder ({size}) found {entry}')
        pass

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

        new_entry = entry.convert(Path(self.working_folder.name), self.migrated_path, remove=self.remove_file(entry))
        if id(new_entry) != id(entry):  # The file was converted and cleaned up
            entry = new_entry  # work on the converted file

        if not self.process_all_files:
            if entry.path.suffix not in entry.all_images:
                if entry.path.suffix in entry.all_movies:
                    self.movie_list.append(entry)
                else:
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
            entry.relocate_file(new_path, register=True,  rollover=True, remove=self.remove_file(entry))
        elif dup_result == SMALL_FILE:  # This file was built by some post processor (apple/windows) importer
            entry.relocate_file(entry.get_new_path(self.small_path), rollover=False, remove=self.remove_file(entry))
        elif dup_result in (GREATER_FILE, LESSER_FILE, EXACT_FILE):
            existing = self.duplicate_get(entry)
            if not entry.path == existing.path:  # We are the same file,  do nothing
                if dup_result in (LESSER_FILE, EXACT_FILE):
                    if entry.folder and entry.folder.custom_folder:  # Special case,  custom folder
                        entry.relocate_file(entry.get_new_path(self.output_folder, invalid_parents=self.bad_parents),
                                            register=True, rollover=True, remove=self.remove_file(entry))
                    else:
                        entry.relocate_file(entry.get_new_path(self.duplicate_path), rollover=False,
                                            remove=self.remove_file(entry))
                elif dup_result == GREATER_FILE:
                    existing.relocate_file(existing.get_new_path(self.duplicate_path),
                                           remove=self.remove_file(existing), rollover=False)
                    entry.relocate_file(new_path, register=True, remove=self.remove_file(entry), rollover=False)
        else:
            assert False, f'Invalid test result {dup_result}'  # pragma: no cover

    def process_folder(self, folder: FolderCleaner):
        self.print(f'. Folder: {folder.path}')
        for entry in folder.path.iterdir():
            if entry.is_dir() and entry not in self.ignore_folders:
                this_folder = FolderCleaner(Path(entry), parent=folder, app_name=self.app_name)
                if this_folder.description in self.bad_parents:
                    this_folder.description = None
                self.process_folder(this_folder)
            elif entry.is_file():
                self.process_file(file_cleaner(entry, folder))

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
            elif self.keep_original_files:
                return False
        return True

