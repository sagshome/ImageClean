# Driver program for restructuring image files.
import getopt
import logging
import os
import sys

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

from Backend.Cleaner import FileCleaner, ImageCleaner, FolderCleaner, file_cleaner


NEW_FILE: int = 0
EXACT_FILE: int = 1
LESSER_FILE: int = 2
GREATER_FILE: int = 3
SMALL_FILE: int = 4

WARNING_FOLDER_SIZE = 100  # Used when auditing directories,  move then 100 members is a Yellow flag


class ImageClean:

    def __init__(self, **kwargs):

        self.config = {
            'recreate': False,
            'keep_duplicates': False,
            'keep_movie_clips': False,
            'keep_converted_files': False,
            'keep_original_files': False,
        }

        for key in kwargs:
            if key in self.config:
                # todo: call the actual function
                self.config[key] = kwargs[key]

        self.process_all_files = False
        self.verbose = False
        self.in_place = False
        self.prepared = False
        self.output_folder = None
        self.input_folder = None
        self.ignore_folders = []
        self.bad_parents = []
        self.no_date_path = None
        self.small_path = None
        self.migrated_path = None
        self.duplicate_path = None
        self.image_movies_path = None

    def set_recreate(self, value: bool):
        self.config['recreate'] = value

    def set_keep_duplicates(self, value: bool):
        self.config['keep_duplicates'] = value

    def set_keep_movie_clips(self, value: bool):
        self.config['keep_movie_clips'] = value

    def set_keep_converted_files(self, value: bool):
        self.config['keep_converted_files'] = value

    def set_keep_original_files(self, value: bool):
        self.config['keep_original_files'] = value

    def set_process_all_files(self, value: bool):
        self.config['process_all_files'] = value

    def add_ignore_folder(self, value: Path):
        self.ignore_folders.append(value)

    def add_bad_parents(self, value: Path):
        self.bad_parents.append(value)

    def set_paranoid(self, value: bool):
        self.set_keep_duplicates(value)
        self.set_keep_original_files(value)
        self.set_keep_converted_files(value)
        self.set_keep_movie_clips(value)

    def prepare(self):
        self.prepared = True
        if not self.output_folder:
            self.output_folder = self.input_folder

        if self.output_folder == self.input_folder:
            if self.config['recreate']:
                assert False, f'Can not recreate with same input/output folders: {self.input_folder}\n\n'
            in_place = True

        # Make sure we ignore these,  they came from us.
        self.ignore_folders.append(self.output_folder.joinpath(movie_path_base))
        self.ignore_folders.append(self.output_folder.joinpath(duplicate_path_base))
        self.ignore_folders.append(self.output_folder.joinpath(converted_path_base))
        self.ignore_folders.append(self.output_folder.joinpath(f'{app_name}_Small'))

        self.no_date_path = self.output_folder.joinpath(f'{app_name}_NoDate')
        self.small_path = self.output_folder.joinpath(f'{app_name}_Small')
        if self.config['keep_converted_files']:
            self.output_folder.joinpath(f'{app_name}_Migrated')

        if self.config['keep_duplicates']:
            self.duplicate_path = self.output_folder.joinpath(f'{app_name}_Duplicates')

        if self.config['keep_movie_clips']:
            self.output_folder.joinpath(f'{app_name}_ImageMovies')


        # Backup any previous attempts

        if not self.config['recreate'] or self.config['in_place']:  # Same root or importing from a new location
            self.register_files(self.output_folder, self.output_folder)

        if self.config['recreate']:
            if self.output_folder.exists():
                os.rename(self.output_folder, f'{self.output_folder}_{datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}')

        os.mkdir(self.output_folder) if not self.output_folder.exists() else None
        os.mkdir(self.no_date_path) if not self.no_date_path.exists() else None
        os.mkdir(self.migrated_path) if self.migrated_path and not self.migrated_path.exists() else None
        os.mkdir(self.duplicate_path) if self.duplicate_path and not self.duplicate_path.exists() else None
        os.mkdir(self.image_movies_path) if self.image_movies_path and not self.image_movies_path.exists() else None
        os.mkdir(self.small_path) if self.small_path and not self.small_path.exists() else None

    def register_files(self, input_dir: Path, base: Path):
        for entry in input_dir.iterdir():
            if entry.is_dir():
                if entry not in self.ignore_folders:
                    self.register_files(entry, base)
            else:
                if not entry.parent == base:  # If this was previously processed it would not be here
                    file_cleaner(entry, FolderCleaner(input_dir)).register()


    @staticmethod
    def duplicate_get(entry: Union[ImageCleaner, FileCleaner]) -> Optional[Union[ImageCleaner, FileCleaner]]:

        for value in entry.get_all_registered():
            if entry == value:  # The image data is exactly the same
                return value
        logger.error(f'Expecting to find a duplicate for {entry.path}')
        return None

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
                    just_name = file_entry.just_name
                    for suffix in file_entry.all_images:
                        if FileCleaner(Path(f'{just_name}{suffix}')).is_registered():
                            if self.image_movies_path:
                                print(f'.... Saving Clip {file_entry.path}')
                                file_entry.relocate_file(self.image_movies_path, remove=True)
                            else:
                                print(f'.... Removing Clip {file_entry.path}')
                                os.unlink(file_entry.path)
                            break


    def audit_folders(self, path: Path) -> List[Path]:
        large_folders = []
        for entry in path.iterdir():
            if entry.is_dir():
                self.audit_folders(entry)
                size = len(os.listdir(entry))
                if size == 0:
                    print(f'  Removing empty folder {entry}') if verbose else None
                    os.rmdir(entry)
                elif size > WARNING_FOLDER_SIZE:
                    large_folders.append(entry)
                    print(f'  VERY large folder ({size}) found {entry}')
        return large_folders

    def process_file(self, entry: Union[FileCleaner, ImageCleaner]):
        """
        Perform any conversions
        Extract image date
        Calculate new destination folder
        Test Duplicate status

        :param entry: Cleaner object,  promoted to a subclass when processed
        """
        print(f'.. File: {entry.path}') if verbose else None

        if not entry.is_valid:
            logger.debug(f'Invalid file {entry.path}')
            return

        new_entry = entry.convert(self.migrated_path, remove=self.config['keep_original_files'] and not self.config['in_place'])
        if id(new_entry) != id(entry):  # The file was converted and cleaned up
            entry = new_entry  # work on the converted file

        if not self.config['process_all_files']:
            if entry.path.suffix not in entry.all_images:
                if entry.path.suffix not in entry.all_movies:
                    logger.debug(f'Ignoring not image file {entry.path}')
                    return

        # Now lets go about building our output folder
        if entry.date:
            new_path = entry.get_new_path(self.output_folder)
        else:  # make sure we do not over process things already determined to not be 'no date' files.
            if str(entry.path.parent).startswith(str(self.no_date_path)):
                new_path = entry.path.parent
            else:
                new_path = entry.get_new_path(self.no_date_path)

        dup_result = self.duplicates_test(entry)
        logger.debug(f'Duplicate Test: {dup_result} - {entry.path}')
        if dup_result == NEW_FILE:  # We have not seen this file before
            entry.relocate_file(new_path, register=True, remove=not keep_original_files or in_place, rollover=True)
        elif dup_result == SMALL_FILE:  # This file was built by some post processor (apple/windows) importer
            entry.relocate_file(entry.get_new_path(small_path), remove=not keep_original_files, rollover=False)
        elif dup_result in (GREATER_FILE, LESSER_FILE, EXACT_FILE):
            existing = self.duplicate_get(entry)
            if dup_result in (LESSER_FILE, EXACT_FILE):
                entry.relocate_file(entry.get_new_path(duplicate_path), remove=not keep_original_files or in_place,
                                    create_dir=False, rollover=False)
            elif dup_result == GREATER_FILE:
                existing.relocate_file(existing.get_new_path(duplicate_path), remove=not keep_original_files,
                                       create_dir=False, rollover=False)
                entry.relocate_file(new_path, register=True, remove=in_place, rollover=False)
        else:
            assert False, f'Invalid test result {dup_result}'

    def process_folder(self, folder: FolderCleaner):
        print(f'. Folder: {folder.path}') if verbose else None
        for entry in folder.path.iterdir():
            if entry.is_dir() and entry not in self.ignore_folders:
                this_folder = FolderCleaner(Path(entry), parent=folder)
                if this_folder.description in self.bad_parents:
                    this_folder.description = None
                self.process_folder(this_folder)
            elif entry.is_file():
                self.process_file(file_cleaner(entry, folder))


app_path = Path(sys.argv[0])
app_name = app_path.name[:len(app_path.name) - len(app_path.suffix)]

duplicate_path_base = f'{app_name}_Duplicates'
movie_path_base = f'{app_name}_Clips'
converted_path_base = f'{app_name}_Converted'

app_help = f'{app_name} -hdmsaruPV -i <ignore_folder>... -n <non_description_folder>... -o <output> input_folder\n' \
           f'Used to clean up directories.' \
           f'\n\n-h: This help' \
           f'\n-d: Save duplicate files into {duplicate_path_base}' \
           f'\n-m: Save movie-clips that are also images (iphone live picture movies) into {movie_path_base}' \
           f'\n-c: Save original images that were successfully converted (HEIC) to JPG into {converted_path_base}'  \
           f'\n-a: Process all files,   ignore anything that is not an image' \
           f'\n-r: Recreate the output folder (not valid without -o)' \
           f'\n-s: safe import, keep original files when processed'\
           f'\n-P: Paranoid,  -d, -m, -j, -s -x' \
           f'\n-V: Verbose,  bather on to stdout' \
           f'\n-o output folder - where to send the output to' \
           f'\n-i ignore folder - if you find this folder name just ignore it' \
           f'\n-n non parent folder - Usually images in a folder are saved with the folder, in this case we ' \
           f'just want to ignore the parent,  example folder "Camera Uploads' \
           f'\n\ninput folder - where to start the processing from' \

log_file = Path.home().joinpath(f'{app_name}.log')
if log_file.exists() and os.stat(log_file).st_size > 100000:
    FileCleaner.rollover_name(log_file)

debugging = os.getenv(f'{app_name.upper()}_DEBUG')
logger = logging.getLogger(app_name)


fh = logging.FileHandler(filename=log_file)
fh_formatter = logging.Formatter('%(asctime)s %(levelname)s %(lineno)d:%(filename)s- %(message)s')
fh.setFormatter(fh_formatter)
logger.addHandler(fh)

if debugging:
    logger.setLevel(level=logging.DEBUG)
    oh = logging.StreamHandler()
    oh.setFormatter(fh_formatter)
    logger.addHandler(oh)
else:
    logger.setLevel(level=logging.ERROR)

if __name__ == '__main__':
    """
    Goals.
    1. Convert HEIC files to JPG
    2. Any root file should move into a dated folder YEAR/MON/DATE
    3. Any file without date info,  should have date into added
    4. Clean up garbage
    5. Clean up duplicates
    
    """
    verbose = False
    start_time = datetime.now()
    logger.debug(f'Starting {app_name} - {start_time}')
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hdmcsarPVo:i:n:', [])
    except getopt.GetoptError:
        print(app_help)
        sys.exit(2)

    app = ImageClean()
    if len(args) != 1:
        print(f'Only one argument <input folder> is required.\n\n')
        print(app_help)
        sys.exit(2)
    else:
        app.input_folder = Path(args[0])
        try:
            os.stat(app.input_folder)
        except FileNotFoundError:
            print(f'Input Folder: {app.input_folder} is not found.   Critical error \n\n {app_help}')
            sys.exit(3)

    for opt, arg in opts:
        if opt == '-h':
            print(app_help)
            sys.exit(2)
        elif opt == '-r':
            app.set_recreate(True)
        elif opt == '-d':
            app.set_keep_duplicates(True)
        elif opt == '-m':
            app.set_keep_movie_clips(True)
        elif opt == '-a':
            app.process_all_files = True
        elif opt == '-c':
            app.set_keep_converted_files(True)
        elif opt == '-s':
            app.set_keep_original_files(True)
        elif opt == '-o':
            app.output_folder = Path(arg)
        elif opt == '-i':
            app.add_ignore_folder(Path(arg))
        elif opt == '-n':
            app.add_bad_parents(Path(arg))
        elif opt == '-V':
            verbose = app.verbose = True
        elif opt == '-P':
            app.set_paranoid(True)
        else:
            print(f'Invalid option: {opt}\n\n')
            print(app_help)
            sys.exit(2)

    print(f'logging to...{log_file}') if verbose else None

    master = FolderCleaner(app.input_folder,
                           parent=None,
                           root_folder=app.input_folder,
                           output_folder=app.output_folder,
                           no_date_folder=app.no_date_path)

    master.description = None
    app.prepare()
    app.process_folder(master)

    # Clean up
    master.reset()
    app.process_duplicates_movies(FolderCleaner(app.no_date_path, root_folder=app.no_date_path))
    suspicious_folders = app.audit_folders(app.output_folder)
    # todo: roll back small files that are unique
    logger.debug(f'Completed ({datetime.now() - start_time}')
