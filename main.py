# This is a sample Python script.
import getopt
import logging
import os
import platform
import sys

from FolderCleaner import FolderCleaner
from FileCleaner import FileCleaner

from datetime import datetime
from pathlib import Path


# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.

# JVaEmRy2S4OwlOwRuUxQQg
# F:\pictures\2014\03\12\20140312-161503\NgDEfEunTpyOpek0X1mOTQ

# Exiv2 Image data standards
# Exif[36867] - Date Take
# 0th[270] - Description
# Exif[37510 - Description (from shotwell) - piexif.ExifIFD.UserComment

duplicates = {}


def process_duplicates(entry: FileCleaner, new_path: str) -> bool:
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
        entry.relocate_file(entry.get_new_path(ignored))
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
            if entry.convert(conversion_type='JPEG', update_file=run_mode):  # converted file lives in original folder
                converted = True
                new_path = entry.get_new_path(base=migrated)
                if run_mode:
                    entry.relocate_file(new_path, update=False)  # The original file has been preserved, we can work on new
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

    if process_duplicates(entry, new_path):
        entry.relocate_file(new_path)
    else:
        entry.relocate_file(entry.get_new_path(duplicate))

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


if platform.system() == 'Linux':
    base_directory = '/shared'
else:
    base_directory = 'F:'

master_directory = f'{base_directory}{os.path.sep}Pictures'
new_directory = f'{base_directory}{os.path.sep}Photos'

app_path = Path(sys.argv[0])
app_name = app_path.name[:len(app_path.name) - len(app_path.suffix)]
test = run = preserve = False

app_help = f'{app_name}-hr -i <inputdir> -o <outputdir> \n' \
           f'Used to clean up directories.' \
           f'\n\n-h: This help' \
           f'\n-r: Run the app (vs just verify)' \
           f'\n-p: Preserve (append to) output directory' \
           f'\n\n-i input folder - where to start the processing from' \
           f'\n-o output directory - where to send the output to'

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
        opts, args = getopt.getopt(sys.argv[1:], 'hrpi:o:', ['input=', 'output='])
    except getopt.GetoptError:
        print(app_help)
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            print(app_help)
            sys.exit(2)
        elif opt == '-r':
            run = True
        elif opt == '-p':
            preserve = True
        elif opt == '-i':
            master_directory = arg
        elif opt == '-o':
            new_directory = arg

    no_date = f'{new_directory}{os.path.sep}NoDate'
    migrated = f'{new_directory}{os.path.sep}Migrated'
    duplicate = f'{new_directory}{os.path.sep}Duplicates'
    ignored = f'{new_directory}{os.path.sep}Ignored'
    image_movies = f'{new_directory}{os.path.sep}ImageMovies'

    run_mode = True if run else False

    if run_mode:
        # Backup any previous attempts
        if not preserve:
            if os.path.exists(new_directory):
                os.rename(new_directory, f'{new_directory}_{datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}')

        os.mkdir(new_directory) if not os.path.exists(new_directory) else None
        os.mkdir(no_date) if not os.path.exists(no_date) else None
        os.mkdir(migrated) if not os.path.exists(migrated) else None
        os.mkdir(duplicate) if not os.path.exists(duplicate) else None
        os.mkdir(ignored) if not os.path.exists(ignored) else None
        os.mkdir(image_movies) if not os.path.exists(image_movies) else None

    process_folder(FolderCleaner(master_directory, master_directory))

    process_duplicates_movies(FolderCleaner(no_date, no_date))

    pass  # Set a breakpoint to see data structures

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
