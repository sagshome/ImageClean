# Driver program for restructuring image files.
import getopt
import logging
import os
import re
import sys

from FolderCleaner import FolderCleaner
from FileCleaner import FileCleaner
from typing import List, Set, Dict, Tuple, Optional

from datetime import datetime
from pathlib import Path


def custom_folder(folder: Path) -> bool:
    """
    A custom folder is a folder that does not end with a date format YYYY/MM/DD but has the date format in it
    :return: boolean  - True if a custom folder

    .../2012/3/3/foobar is custom
    .../foo/bar is NOT custom
    .../2012/3/3 is NOT managed
    """

    return not re.match('^.*[0-9]{4}.[0-9]{1,2}.[0-9]{1,2}.+', str(folder))


def populate_duplicates(input_dir: FolderCleaner, base: Path):
    for entry in input_dir.path.iterdir():
        if entry.is_dir():
            folder = FolderCleaner(entry, base)
            populate_duplicates(folder, base)
        else:
            if not entry == new_directory:  # If this was previously processed it would not be here
                existing = FileCleaner(entry, input_dir)
                existing.register()


def process_duplicates(entry: FileCleaner) -> bool:
    """
    Do some duplicate processing.   We have two kinds of folders,  custom (a name) and unmanaged (a date).  If we
    find the new file was going into a unmanaged directory and we have a managed version,  we just want to keep that
    and ignore the first.   The later is also true.
    :param entry: The definition of the current file
    :return: boolean,   A False for this is a duplicate
    """

    if not entry.is_registered():
        return True  # This is a new FileCleaner object.

    new_path = entry.get_new_path(new_directory)
    if entry.is_registered(by_file=True, by_path=True, alternate_path=new_path):  # A exact version of this exists
        return False

    if entry.is_registered(by_file=True, by_path=False):  # Same name/file but going for a different folder
        existing = entry.get_registered(by_file=True, by_path=False)
        existing_custom = custom_folder(existing.file.parent)
        new_custom = custom_folder(new_path)
        if existing_custom and not new_custom:
            return False  # We are a duplicate and the existing file has precedence
        elif not existing_custom and new_custom:
            os.unlink(existing.file)
            existing.de_register()
            # todo: maybe we should move this to duplicates to
            return True  # We are custom and the existing was not,  cleanup and continue
        elif existing_custom and new_custom:  # The exact same file but in different paths .../family,  .../picnics
            return False  # First in wins   (alternately we could save both)
        elif not existing_custom and not new_custom:  # This should be impossible without human finger issues
            if existing.parent.date < entry.folder.folder_time or existing.entry.date == entry.folder.folder_time:
                return False
            elif existing.parent.date > entry.folder.folder_time:
                os.unlink(existing.file)
                existing.de_register()
                return True  # We are custom and the existing was not,  cleanup and continue

    if entry.is_registered(by_path=True, by_file=False, alternate_path=new_path):  # Same name, same path, different
        entry.get_registered(by_path=True, by_file=False, alternate_path=new_path).rollover_name()
        return True
    return True


def process_duplicates_movies(movie_dir):
    for entry in movie_dir.path.iterdir():
        if entry.is_dir():
            # logging.debug(f'Found directory {entry}')
            process_duplicates_movies(FolderCleaner(Path(entry), movie_dir.root_directory, parent=movie_dir))
        elif entry.is_file():
            file_entry = FileCleaner(Path(entry), folder=movie_dir)
            if file_entry.file.suffix in file_entry.all_movies:
                just_name = file_entry.just_name
                for suffix in file_entry.all_images:
                    if FileCleaner(f'{just_name}{suffix}').is_registered():
                        if image_movies:
                            print(f'.... Saving Clip {file_entry.file}')
                            file_entry.relocate_file(image_movies, remove=True)
                        else:
                            print(f'.... Remving Clip {file_entry.file}')
                            os.unlink(file_entry.file)
                        break


def process_file(entry: FileCleaner):
    print(f'.. File: {entry.file}') if verbose else None
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
        entry.register()
    else:
        entry.relocate_file(entry.get_new_path(duplicate)) if duplicate else None  # Relocation updates the path.

    if converted and preserve_file:
        os.unlink(preserve_file)


def process_folder(folder: FolderCleaner):
    print(f'Folder: {folder.path}') if verbose else None
    for entry in folder.path.iterdir():
        if entry.is_dir():
            process_folder(FolderCleaner(Path(entry), folder.root_directory, folder))
        elif entry.is_file():
            process_file(FileCleaner(Path(entry), folder=folder))


app_path = Path(sys.argv[0])
app_name = app_path.name[:len(app_path.name) - len(app_path.suffix)]
test = run = preserve = False

app_help = f'{app_name} -hpdmjPV -i <ignore_this_folder> -n <non_description_folder> -o <output> input_folder\n' \
           f'Used to clean up directories.' \
           f'\n\n-h: This help' \
           f'\n-r: Recreate the output directory' \
           f'\n-d: Create a directory to store duplicate files' \
           f'\n-m: Create a directory to store movie-clips that are also images (iphone live picture movies)' \
           f'\n-j: Create a folder to store things we find that are not images, movies etc.' \
           f'\n-s: Save original images that were successfully converted (HEIC) to JPG' \
           f'\n-P: Paranoid,  DO NOT REMOVE ANYTHING - all files preserved.' \
           f'\n-V: Verbose,  Display what you are working on.' \
           f'\n-o output directory - where to send the output to' \
           f'\n-i ignore directory - if you find this directory just ignore it' \
           f'\n-n non parent directory - Usually images in a folder are saved with the folder, in this case we ' \
           f'just want to ignore the parent,  example folder "Camera Uploads' \
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
        opts, args = getopt.getopt(sys.argv[1:], 'hrdmjsPVo:i:n:', [])
    except getopt.GetoptError:
        print(app_help)
        sys.exit(2)

    preserve = True
    keep_duplicates = False
    keep_movie_clips = False
    keep_junk_files = False
    save_converted_files = False
    in_place = False
    verbose = False
    new_directory = None
    ignore_folders = []
    bad_parents = []

    if len(args) != 1:
        print(f'Missing input directory\n\n')
        print(app_help)
        sys.exit(2)
    else:
        master_directory = args[0]

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
            new_directory = Path(arg)
        elif opt == '-i':
            ignore_folders.append(arg)
        elif opt == '-n':
            bad_parents.append(arg)
        elif opt == '-V':
            verbose = True
        elif opt == '-P':
            keep_duplicates = True
            keep_movie_clips = True
            keep_junk_files = True
            save_converted_files = True
        else:
            print(f'Invalid option: {opt}\n\n')
            print(app_help)
            sys.exit(2)

    try:
        os.stat(master_directory)
    except FileNotFoundError:
        print(app_help)
        sys.exit(2)

    master_directory = Path(master_directory)
    if not new_directory:
        new_directory = master_directory  # Going to update in place

    if new_directory == master_directory:
        preserve = True
        in_place = True

    no_date = Path(f'{new_directory}{os.path.sep}NoDate')
    migrated = Path(f'{new_directory}{os.path.sep}Migrated') if save_converted_files else None
    duplicate = Path(f'{new_directory}{os.path.sep}Duplicates') if keep_duplicates else None
    ignored = Path(f'{new_directory}{os.path.sep}Ignored') if keep_junk_files else None
    image_movies = Path(f'{new_directory}{os.path.sep}ImageMovies') if keep_movie_clips else None

    # Backup any previous attempts
    if preserve:
        populate_duplicates(FolderCleaner(new_directory, new_directory), new_directory)
    else:
        if os.path.exists(new_directory):
            os.rename(new_directory, f'{new_directory}_{datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}')

    os.mkdir(new_directory) if not os.path.exists(new_directory) else None
    os.mkdir(no_date) if not os.path.exists(no_date) else None
    os.mkdir(migrated) if migrated and not os.path.exists(migrated) else None
    os.mkdir(duplicate) if duplicate and not os.path.exists(duplicate) else None
    os.mkdir(ignored) if ignored and not os.path.exists(ignored) else None
    os.mkdir(image_movies) if image_movies and not os.path.exists(image_movies) else None

    master = FolderCleaner(master_directory, master_directory)
    master.description = None
    master.parent = None
    process_folder(master)

    process_duplicates_movies(FolderCleaner(Path(no_date), no_date))

    pass  # Set a breakpoint to see data structures

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
