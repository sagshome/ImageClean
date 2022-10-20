"""
Command line call for Cleaning
"""
# pylint: disable=line-too-long

import getopt
import logging
import os
import sys

from datetime import datetime
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))

from Backend.cleaner import FileCleaner
from Backend.ImageClean import ImageClean


APP_PATH = Path(sys.argv[0])
APP_NAME = APP_PATH.name[:len(APP_PATH.name) - len(APP_PATH.suffix)]
LOGGER_NAME = 'Cleaner'  # I am hard-coding this value since I call it from cmdline and UI which have diff names

app = ImageClean(LOGGER_NAME)  # Sets all default values

APP_HELP = f'{APP_NAME} -hdmsaruPV -i <ignore_folder>... -n <non_description_folder>... -o <output> input_folder\n' \
           f'Used to clean up directories.' \
           f'\n\n-h: This help' \
           f'\n-d: Save duplicate files into {app.duplicate_path_base}' \
           f'\n-m: Save movie-clips that are images (iphone live picture movies) into {app.image_movies_path_base}' \
           f'\n-c: Save original images that were successfully converted (HEIC) to JPG into {app.migrated_path_base}' \
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

log_file = Path.home().joinpath(f'{LOGGER_NAME}.log')
if log_file.exists() and os.stat(log_file).st_size > 100000:
    FileCleaner.rollover_name(log_file)

debugging = os.getenv(f'{LOGGER_NAME.upper()}_DEBUG')
logger = logging.getLogger(LOGGER_NAME)

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
    logger.debug('Starting %s - %s', APP_NAME, start_time)
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hdmcsarPVo:i:n:', [])
    except getopt.GetoptError:
        print(f'Invalid syntax: {sys.argv[1:]}\n\n')
        print(APP_HELP)
        sys.exit(2)

    if len(args) != 1:
        print(f'Only one argument <input folder> is required.\n\n')
        print(APP_HELP)
        sys.exit(2)
    else:
        app.input_folder = Path(args[0])
        try:
            os.stat(app.input_folder)
        except FileNotFoundError:
            print(f'Input Folder: {app.input_folder} is not found.   Critical error \n\n {APP_HELP}')
            sys.exit(3)

    output = None
    for opt, arg in opts:
        if opt == '-h':
            print(APP_HELP)
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
            output = arg
        elif opt == '-i':
            app.add_ignore_folder(Path(arg))
        elif opt == '-n':
            app.add_bad_parents(Path(arg))
        elif opt == '-V':
            verbose = app.verbose = True
        elif opt == '-P':
            app.set_paranoid(True)

    app.output_folder = Path(output) if output else app.input_folder
    if verbose:
        print(f'logging to...{log_file}')
    app.run()
    # todo: roll back small files that are unique
    logger.debug('Completed (%s - %s)', datetime.now(), start_time)
