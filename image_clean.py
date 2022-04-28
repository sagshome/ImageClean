# Driver program for restructuring image files.
import getopt
import logging
import os
import platform
import sys

from FolderCleaner import FolderCleaner
from FileCleaner import FileCleaner

from datetime import datetime
from pathlib import Path


duplicates = {}  # This hash is used to store processed files so we can detect increments


def populate_duplicates(output: Path):
    for entry in output.iterdir():
        if entry.is_dir():
            populate_duplicates(entry)
        else:
            existing = FileCleaner(entry)
            key_name = existing.file.name.upper()

            if key_name not in duplicates:
                duplicates[key_name] = []
                duplicates[key_name].append(existing)
            else:
                duplicates[key_name].append(existing)


def process_duplicates(entry: FileCleaner) -> bool:
    """
    Do some duplicate processing.   We have two kinds of folders,  managed (a name) and unmanaged (a date).  If we
    find the new file was going into a unmanaged directory and we have a managed version,  we just want to keep that
    and ignore the first.   The later is also true.
    :param entry: The definition of the current file
    :param new_path:  Where we plan on moving it to
    :return: boolean,   A False for this is a duplicate
    """

    key_name = entry.file.name.upper()
    new_path = entry.get_new_path(new_directory)

    if key_name not in duplicates:
        duplicates[key_name] = []
        duplicates[key_name].append(entry)  # This only works because of a side effect with relocate file
        return True  # We are new,  thus unique

    logging.debug(f'Potential dup with {len(duplicates[key_name])} -> {entry.file} -> {new_path}')

    for element in duplicates[key_name]:
        if entry == element:
            return False  # We have an identical match,  no point in going further

        if entry > element:  # This exact file (name, size) is better
            old_entry = FileCleaner(duplicates[key_name].file)
            duplicates[key_name].relocate_file(duplicates[key_name].get_new_path(duplicate))
            logging.debug(f'Moving {old_entry.file} to {duplicate}')
            os.unlink(old_entry.file)
        elif entry < element:  # This exact file (name, size) is better
            pass
        elif entry.file.name == element.file.name and str(element.file.parent) == new_path:
            logging.debug(f'True duplicates {entry.file}  - rolling over name ')
            entry.rollover_name(new_path)
            break
    duplicates[key_name].append(entry)

    return True


def process_duplicates_movies(movie_dir):
    for entry in movie_dir.path.iterdir():
        if entry.is_dir():
            # logging.debug(f'Found directory {entry}')
            folder_entry = FolderCleaner(Path(entry), movie_dir.root_directory)
            folder_entry.parent = movie_dir
            process_duplicates_movies(folder_entry)
        elif entry.is_file():
            file_entry = FileCleaner(Path(entry))
            file_entry.parent = movie_dir  # Allow me to back track
            if file_entry.file.suffix in file_entry.all_movies:
                just_name = file_entry.just_name
                for suffix in file_entry.all_images:
                    if f'{just_name}{suffix}' in duplicates:
                        file_entry.relocate_file(image_movies, remove=True)
                        break


def process_file(entry: FileCleaner):
    if entry.file.suffix not in entry.all_pictures:  # todo: why not have other processing like documents?
        entry.relocate_file(entry.get_new_path(ignored)) if ignored else None
        return
    if not entry.is_valid:
        logging.debug(f'Invalid file {entry.file}')
        return

    converted = False  # We need to clean up the files we converted
    preserve_file = None

    if entry.file.suffix in entry.files_to_convert:
        new_file = Path(entry.conversion_filename("JPEG"))
        if os.path.exists(new_file):
            logging.debug(f'Will not convert {entry.file}, {new_file} already exists')
        else:
            logging.debug(f'Going to covert {entry.file} to JPEG')
            if entry.convert(conversion_type='JPEG'):  # converted file lives in original folder
                converted = True
                if migrated:
                    new_path = entry.get_new_path(base=migrated)
                    entry.relocate_file(new_path, update=False)  # The original has been preserved, we can work on new
                # Now we will work on this new converted file
                entry.file = Path(entry.conversion_filename("JPEG"))
                preserve_file = entry.file
                entry.stat = os.stat(entry.file)

    entry.date = entry.get_date_from_image()
    if not entry.date:
        entry.date = entry.date_from_structure()
        if entry.date:
            entry.update_image()  # No data from image but got one from structure - update it.

    # Now lets go about building our output directory
    new_path = entry.get_new_path(new_directory) if entry.date else entry.get_new_path(no_date)

    if process_duplicates(entry):
        entry.relocate_file(new_path)
    else:
        entry.relocate_file(entry.get_new_path(duplicate)) if duplicate else None

    if converted and preserve_file:
        os.unlink(preserve_file)


def process_folder(folder: FolderCleaner):
    for entry in folder.path.iterdir():
        if entry.is_dir():
            # logging.debug(f'Found directory {entry}')
            folder_entry = FolderCleaner(Path(entry), folder.root_directory)
            folder_entry.parent = folder
            process_folder(folder_entry)
        elif entry.is_file():
            file_entry = FileCleaner(Path(entry))
            file_entry.parent = folder  # Allow me to back track
            process_file(file_entry)


app_path = Path(sys.argv[0])
app_name = app_path.name[:len(app_path.name) - len(app_path.suffix)]
test = run = preserve = False

app_help = f'{app_name}-hpdmj -o <output> input_folder\n' \
           f'Used to clean up directories.' \
           f'\n\n-h: This help' \
           f'\n-r: Recreate the output directory' \
           f'\n-d: Create a directory to store duplicate files' \
           f'\n-m: Create a directory to store movie-clips that are also images (iphone live picture movies)' \
           f'\n-j: Create a folder to store things we find that are not images, movies etc.' \
           f'\n-s: Save original images that were successfully converted (HEIC) to JPG' \
           f'\n\ninput folder - where to start the processing from' \
           f'\n-o output directory - where to send the output to' \
           f'\n\ninput folder - where to start the processing from' \

log_file = f'{os.environ.get("HOME")}{os.path.sep}{app_name}.log'
if os.path.exists(log_file):
    os.remove(log_file)
print(f'logging to...{log_file}')

logging.basicConfig(filename=log_file,
                    format='%(levelname)s:%(asctime)s:%(levelno)s:%(message)s',
                    level=logging.DEBUG)

if __name__ == '__main__':
    """
    Goals.
    1. Convert HEIC files to JPG
    2. Any root file should move into a dated directory YEAR/MON/DATE
    3. Any file without date info,  should have date into added
    4. Clean up garbage
    5. Clean up duplicates
    
    """

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hrdmjso:', ['input=', 'output='])
    except getopt.GetoptError:
        print(app_help)
        sys.exit(2)

    preserve = True
    keep_duplicates = False
    keep_movie_clips = False
    keep_junk_files = False
    save_converted_files = False
    new_directory = None

    for opt, arg in opts:
        if opt == '-h' or len(args) != 1:
            print(app_help)
            sys.exit(2)
        elif opt == '-r':
            preserve = False
        elif opt == '-d':
            keep_duplicates = True
        elif opt == '-m':
            keep_movie_clips = True
        elif opt == '-j':
            keep_junk_files = True
        elif opt == '-s':
            save_converted_files = True
        elif opt == '-o':
            new_directory = arg

    master_directory = args[0]  # Tested this while process options
    try:
        os.stat(master_directory)
    except FileNotFoundError:
        print(app_help)
        sys.exit(2)

    if not new_directory:
        new_directory = master_directory  # Going to update in place

    if new_directory == master_directory:
        preserve = True

    no_date = f'{new_directory}{os.path.sep}NoDate'
    migrated = f'{new_directory}{os.path.sep}Migrated' if save_converted_files else None
    duplicate = f'{new_directory}{os.path.sep}Duplicates' if keep_duplicates else None
    ignored = f'{new_directory}{os.path.sep}Ignored' if keep_junk_files else None
    image_movies = f'{new_directory}{os.path.sep}ImageMovies' if keep_movie_clips else None

    # Backup any previous attempts
    if preserve:
        populate_duplicates(Path(new_directory))
    else:
        if os.path.exists(new_directory):
            os.rename(new_directory, f'{new_directory}_{datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}')

    os.mkdir(new_directory) if not os.path.exists(new_directory) else None
    os.mkdir(no_date) if not os.path.exists(no_date) else None
    os.mkdir(migrated) if migrated and not os.path.exists(migrated) else None
    os.mkdir(duplicate) if duplicate and not os.path.exists(duplicate) else None
    os.mkdir(ignored) if ignored and not os.path.exists(ignored) else None
    os.mkdir(image_movies) if image_movies and not os.path.exists(image_movies) else None

    process_folder(FolderCleaner(master_directory, master_directory))

    process_duplicates_movies(FolderCleaner(Path(no_date), no_date))

    pass  # Set a breakpoint to see data structures

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
