# Driver program for restructuring image files.
import getopt
import logging
import os
import sys

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

from Cleaner import FileCleaner, ImageCleaner, FolderCleaner, file_cleaner


NEW_FILE: int = 0
EXACT_FILE: int = 1
LESSER_FILE: int = 2
GREATER_FILE: int = 3
SMALL_FILE: int = 4

WARNING_FOLDER_SIZE = 100  # Used when auditing directories,  move then 100 members is a Yellow flag


def register_files(input_dir: Path, base: Path):
    for entry in input_dir.iterdir():
        if entry.is_dir():
            if entry not in ignore_folders:
                register_files(entry, base)
        else:
            if not entry.parent == base:  # If this was previously processed it would not be here
                existing = FileCleaner(entry, FolderCleaner(input_dir))
                existing.register()


def duplicate_get(entry: Union[ImageCleaner, FileCleaner]) -> Optional[Union[ImageCleaner, FileCleaner]]:

    for value in entry.get_all_registered():
        if entry == value:  # The image data is exactly the same
            return value
    logging.error(f'Expecting to find a duplicate for {entry.path}')
    return None


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
                    elif entry.folder.date < value.folder.date:
                        return GREATER_FILE
                    else:
                        return LESSER_FILE
                elif entry.date < value.date:
                    return GREATER_FILE
                else:
                    return LESSER_FILE
    return result


def process_duplicates_movies(movie_dir):
    for entry in movie_dir.path.iterdir():
        if entry.is_dir():
            process_duplicates_movies(FolderCleaner(Path(entry), movie_dir.root_folder, parent=movie_dir))
        elif entry.is_file():
            file_entry = FileCleaner(Path(entry), folder=movie_dir)
            if file_entry.path.suffix in file_entry.all_movies:
                just_name = file_entry.just_name
                for suffix in file_entry.all_images:
                    if FileCleaner(Path(f'{just_name}{suffix}')).is_registered():
                        if image_movies_path:
                            print(f'.... Saving Clip {file_entry.path}')
                            file_entry.relocate_file(image_movies_path, remove=True)
                        else:
                            print(f'.... Removing Clip {file_entry.path}')
                            os.unlink(file_entry.path)
                        break


def audit_folders(path: Path) -> List[Path]:
    large_folders = []
    for entry in path.iterdir():
        if entry.is_dir():
            audit_folders(entry)
            size = len(os.listdir(entry))
            if size == 0:
                print(f'  Removing empty folder {entry}') if verbose else None
                os.rmdir(entry)
            elif size > WARNING_FOLDER_SIZE:
                large_folders.append(entry)
                print(f'  VERY large folder ({size}) found {entry}')
    return large_folders


def process_file(entry: Union[FileCleaner, ImageCleaner]):
    """
    Perform any conversions
    Extract image date
    Calculate new destination folder
    Test Duplicate status

    :param entry: Cleaner object,  promoted to a subclass when processed
    """
    print(f'.. File: {entry.path}') if verbose else None

    if not entry.is_valid:
        logging.debug(f'Invalid file {entry.path}')
        return

    migration_path = entry.get_new_path(base=migrated_path) if keep_converted_file else None
    new_entry = entry.convert(migration_path, remove=keep_original_files and not in_place)
    if id(new_entry) != id(entry):  # The file was converted and cleaned up
        entry = new_entry  # work on the converted file

    if not process_all_files:
        if entry.path.suffix not in entry.all_images:
            if entry.path.suffix not in entry.all_movies:
                logging.debug(f'Ignoring not image file {entry.path}')
                return

    # Now lets go about building our output folder
    if entry.date:
        new_path = entry.get_new_path(output_folder)
    else:  # make sure we do not over process things already determined to not be 'no date' files.
        if str(entry.path.parent).startswith(str(no_date_path)):
            new_path = entry.path.parent
        else:
            new_path = entry.get_new_path(no_date_path)

    dup_result = duplicates_test(entry)
    logging.debug(f'Duplicate Test: {dup_result} - {entry.path}')
    if dup_result == NEW_FILE:  # We have not seen this file before
        entry.relocate_file(new_path, register=True, remove=not keep_original_files or in_place, rollover=True)
    elif dup_result == SMALL_FILE:  # This file was built by some post processor (apple/windows) importer
        entry.relocate_file(entry.get_new_path(small_path), remove=not keep_original_files, rollover=False)
    elif dup_result in (GREATER_FILE, LESSER_FILE, EXACT_FILE):
        existing = duplicate_get(entry)
        if dup_result in (LESSER_FILE, EXACT_FILE):
            entry.relocate_file(entry.get_new_path(duplicate_path), remove=not keep_original_files or in_place, create_dir=False, rollover=False)
        elif dup_result == GREATER_FILE:
            existing.relocate_file(existing.get_new_path(duplicate_path), remove=not keep_original_files, create_dir=False, rollover=False)
            entry.relocate_file(new_path, register=True, remove=(in_place or not safe_import), rollover=True)
    else:
        assert False, f'Invalid test result {dup_result}'


def process_folder(folder: FolderCleaner):
    print(f'. Folder: {folder.path}') if verbose else None
    for entry in folder.path.iterdir():
        if entry.is_dir() and entry not in ignore_folders:
            this_folder = FolderCleaner(Path(entry), parent=folder)
            if this_folder.description in bad_parents:
                this_folder.description = None
            process_folder(this_folder)
        elif entry.is_file():
            process_file(file_cleaner(entry, folder))


app_path = Path(sys.argv[0])
app_name = app_path.name[:len(app_path.name) - len(app_path.suffix)]

duplicate_path_base = f'{app_name}_Duplicates'
movie_path_base = f'{app_name}_Clips'
converted_path_base = f'{app_name}_Converted'

app_help = f'{app_name} -hdmsaruPV -i <ignore_this_folder>... -n <non_description_folder>... -o <output> input_folder\n' \
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


log_file = f'{os.environ.get("HOME")}{os.path.sep}{app_name}.log'
FileCleaner.rollover_name(Path(log_file))

logging.basicConfig(filename=log_file,
                    # format='%(levelname)s:%(asctime)s:%(levelno)s:%(message)s',
                    format='%(levelname)s:%(levelno)s:%(message)s',
                    level=logging.DEBUG)

if __name__ == '__main__':
    """
    Goals.
    1. Convert HEIC files to JPG
    2. Any root file should move into a dated folder YEAR/MON/DATE
    3. Any file without date info,  should have date into added
    4. Clean up garbage
    5. Clean up duplicates
    
    """

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hdmcsarPVo:i:n:', [])
    except getopt.GetoptError:
        print(app_help)
        sys.exit(2)

    recreate = False
    keep_duplicates = False
    keep_movie_clips = False
    keep_converted_files = False
    keep_original_files = False
    process_all_files = False
    in_place = False
    verbose = False
    output_folder = None
    ignore_folders = []
    bad_parents = []

    if len(args) != 1:
        print(f'Only one argument <input folder> is required.\n\n')
        print(app_help)
        sys.exit(2)
    else:
        input_folder = args[0]
        try:
            os.stat(input_folder)
        except FileNotFoundError:
            print(f'Input Folder: {input_folder} is not found.   Critical error \n\n {app_help}')
            sys.exit(3)

    for opt, arg in opts:
        if opt == '-h':
            print(app_help)
            sys.exit(2)
        elif opt == '-r':
            recreate = True
        elif opt == '-d':
            keep_duplicates = True
        elif opt == '-m':
            keep_movie_clips = True
        elif opt == '-a':
            process_all_files = True
        elif opt == '-c':
            keep_converted_files = True
        elif opt == '-s':
            keep_original_files = True
        elif opt == '-o':
            output_folder = Path(arg)
        elif opt == '-i':
            ignore_folders.append(arg)
        elif opt == '-n':
            bad_parents.append(arg)
        elif opt == '-V':
            verbose = True
        elif opt == '-P':
            keep_duplicates = True
            keep_movie_clips = True
            keep_converted_file = True
            keep_original_files = True
        else:
            print(f'Invalid option: {opt}\n\n')
            print(app_help)
            sys.exit(2)

    print(f'logging to...{log_file}') if verbose else None

    input_folder = Path(input_folder)
    if not output_folder:
        output_folder = input_folder  # Going to update in place

    if output_folder == input_folder:
        if recreate:
            print(f'Can not recreate with same input/output folders: {input_folder}\n\n')
            print(app_help)
            sys.exit(3)
        in_place = True

    # Make sure we ignore these,  they came from us.
    ignore_folders.append(Path(f'{output_folder}{os.path.sep}{movie_path_base}'))
    ignore_folders.append(Path(f'{output_folder}{os.path.sep}{duplicate_path_base}'))
    ignore_folders.append(Path(f'{output_folder}{os.path.sep}{converted_path_base}'))
    ignore_folders.append(Path(f'{output_folder}{os.path.sep}{app_name}_Small'))

    no_date_path = Path(f'{output_folder}{os.path.sep}{app_name}_NoDate')
    small_path = Path(f'{output_folder}{os.path.sep}{app_name}_Small')
    migrated_path = Path(f'{output_folder}{os.path.sep}{app_name}_Migrated') if keep_converted_file else None
    duplicate_path = Path(f'{output_folder}{os.path.sep}{app_name}_Duplicates') if keep_duplicates else None
    image_movies_path = Path(f'{output_folder}{os.path.sep}{app_name}_ImageMovies') if keep_movie_clips else None

    master = FolderCleaner(input_folder,
                           parent=None,
                           root_folder=input_folder,
                           output_folder=output_folder,
                           no_date_folder=no_date_path)

    # Backup any previous attempts

    if not recreate or in_place:  # Same root or importing from a new location
        register_files(output_folder, output_folder)

    if recreate:
        if os.path.exists(output_folder):
            os.rename(output_folder, f'{output_folder}_{datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}')

    os.mkdir(output_folder) if not os.path.exists(output_folder) else None
    os.mkdir(no_date_path) if not os.path.exists(no_date_path) else None
    os.mkdir(migrated_path) if migrated_path and not os.path.exists(migrated_path) else None
    os.mkdir(duplicate_path) if duplicate_path and not os.path.exists(duplicate_path) else None
    os.mkdir(image_movies_path) if image_movies_path and not os.path.exists(image_movies_path) else None
    os.mkdir(small_path) if small_path and not os.path.exists(small_path) else None

    master.description = None
    process_folder(master)

    # Clean up
    master.reset()
    process_duplicates_movies(FolderCleaner(Path(no_date_path), root_folder=no_date_path))
    suspicious_folders = audit_folders(output_folder)
    # todo: roll back small files that are unique
    logging.debug('Completed')
