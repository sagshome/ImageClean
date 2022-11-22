"""
Command line call for Cleaning

Goals.
1. Convert HEIC files to JPG
2. Any root file should move into a dated folder YEAR/MON/DATE
3. Any file without date info,  should have date into added
4. Clean up garbage
5. Clean up duplicates
"""
# pylint: disable=line-too-long

import getopt
import logging
import os
import sys

from datetime import datetime
from pathlib import Path
from backend.cleaner import FileCleaner  # pylint: disable=wrong-import-position
from backend.image_clean import ImageClean  # pylint: disable=wrong-import-position


APP_PATH = Path(sys.argv[0])
APP_NAME = APP_PATH.name[:len(APP_PATH.name) - len(APP_PATH.suffix)]
LOGGER_NAME = 'Cleaner'  # I am hard-coding this value since I call it from cmdline and UI which have diff names

APP = ImageClean(LOGGER_NAME)  # Sets all default values

APP_HELP = f'{APP_NAME} -hdmsaruPV -i <ignore_folder>... -n <non_description_folder>... -o <output> input_folder\n' \
           f'Used to clean up directories.' \
           f'\n\n-h: This help' \
           f'\n-d: Save duplicate files into {APP.duplicate_path_base}' \
           f'\n-m: Save movie-clips that are images (iphone live picture movies) into {APP.image_movies_path_base}' \
           f'\n-c: Save original images that were successfully converted (HEIC) to JPG into {APP.migrated_path_base}' \
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

log_file = Path.home().joinpath(f'{LOGGER_NAME}.log')  # pylint: disable=invalid-name
if log_file.exists() and os.stat(log_file).st_size > 100000:
    FileCleaner.rollover_name(log_file)

logger = logging.getLogger(LOGGER_NAME)  # pylint: disable=invalid-name

FH = logging.FileHandler(filename=log_file)
FH_FORMATTER = logging.Formatter('%(asctime)s %(levelname)s %(lineno)d:%(filename)s- %(message)s')
FH.setFormatter(FH_FORMATTER)
logger.addHandler(FH)  # pylint: disable=invalid-name

if os.getenv(f'{LOGGER_NAME.upper()}_DEBUG'):
    # pylint: disable=invalid-name
    logger.setLevel(level=logging.DEBUG)
    oh = logging.StreamHandler()
    oh.setFormatter(FH_FORMATTER)
    logger.addHandler(oh)
else:
    logger.setLevel(level=logging.ERROR)


if __name__ == '__main__':
    # pylint: disable=invalid-name
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
        print('Only one argument <input folder> is required.\n\n')
        print(APP_HELP)
        sys.exit(2)
    else:
        APP.input_folder = Path(args[0])
        try:
            os.stat(APP.input_folder)
        except FileNotFoundError:
            print(f'Input Folder: {APP.input_folder} is not found.   Critical error \n\n {APP_HELP}')
            sys.exit(3)

    output = None
    for opt, arg in opts:
        if opt == '-h':
            print(APP_HELP)
            sys.exit(2)
        elif opt == '-r':
            APP.set_recreate(True)
        elif opt == '-d':
            APP.set_keep_duplicates(True)
        elif opt == '-m':
            APP.set_keep_movie_clips(True)
        elif opt == '-c':
            APP.set_keep_converted_files(True)
        elif opt == '-s':
            APP.set_keep_original_files(True)
        elif opt == '-o':
            output = arg
        elif opt == '-i':
            APP.add_ignore_folder(Path(arg))
        elif opt == '-n':
            APP.add_bad_parents(Path(arg))
        elif opt == '-V':
            verbose = APP.verbose = True
        elif opt == '-P':
            APP.set_paranoid(True)

    APP.output_folder = Path(output) if output else APP.input_folder
    if verbose:
        print(f'logging to...{log_file}')
    APP.run()
    logger.debug('Completed (%s - %s)', datetime.now(), start_time)
