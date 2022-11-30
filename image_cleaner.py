"""
Command line call for Cleaning

Goals.
1. Convert HEIC files to JPG  - Only if requested and only if on Linux systems
    (macs support them,  windows can't process them)
2. Any root folder file should move into a dated folder YEAR/MON/DATE
3. SubFolders,  with a 'dated parent' should be imported with that date.  2002-02-02 Picnic / swimming / img01.jpg
3. Any file without date info and not in a dated parent,  moves into - no date folder
5. no date folder is always processed incase I set the date.
4. garbage is ignored
5. Clean up duplicates
"""
# pylint: disable=line-too-long
import asyncio
import getopt
import logging
import os
import sys

from datetime import datetime
from pathlib import Path

sys.path.append('.')
from backend.cleaner import FileCleaner  # pylint: disable=wrong-import-position import-error
from backend.image_clean import ImageClean  # pylint: disable=wrong-import-position import-error


APP_PATH = Path(sys.argv[0])
APP_NAME = APP_PATH.name[:len(APP_PATH.name) - len(APP_PATH.suffix)]

LOGGER_NAME = 'Cleaner'  # I am hard-coding this value since I call it from cmdline and UI which have diff app names
APP = ImageClean(LOGGER_NAME)  # Sets all default values

APP_HELP = f'{APP_NAME} -hcrsv -i <import_folder> image_folder\n' \
           '\n\n-h: This help' \
           '\nThis application will reorganize image files into a folder structure that is human friendly' \
           '\nGo to https://github.com/sagshome/ImageClean/wiki for details' \
           f'\n\n-c: Converted (HEIC) files to JPG files. The original HEIC files are saved into the "{APP.migrated_path_base}" folder' \
           '\n-r: Remove imported files. if the file is imported successfully,  the original file is removed'\
           f'\n-s: Check for small files (save in "{APP.small_base}" folder) - This WILL slow down processing' \
           '\n-v: Verbose,  blather on to the terminal' \
           '\n-i import folder - where we are importing from (default is just process image_folder)' \
           '\n\nimage folder - where to image files are saved'

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


async def run():
    """
    This is needed to support async requirement of APP.run()
    :return:
    """
    await APP.run()


if __name__ == '__main__':
    # pylint: disable=invalid-name
    verbose = False
    start_time = datetime.now()
    logger.debug('Starting %s - %s', APP_NAME, start_time)
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hcrsvi:', [])
    except getopt.GetoptError:
        print(f'Invalid syntax: {sys.argv[1:]}\n\n')
        print(APP_HELP)
        sys.exit(2)

    if len(args) != 1:
        print('\nimage folder is required.\n\n')
        print(APP_HELP)
        sys.exit(2)
    else:
        APP.output_folder = Path(args[0])

    input_folder = None
    for opt, arg in opts:
        if opt == '-h':
            print(APP_HELP)
            sys.exit(2)
        elif opt == '-c':
            APP.convert_files = True
        elif opt == '-r':
            APP.keep_original_files = False
        elif opt == '-s':
            APP.process_small_files = True
        elif opt == '-v':
            verbose = APP.verbose = True
        elif opt == '-i':
            try:
                os.stat(arg)
            except FileNotFoundError:
                print(f'Import Folder: {arg} is not found.   Critical error \n\n {APP_HELP}')
                sys.exit(3)
            input_folder = Path(arg)

    APP.input_folder = APP.output_folder if not input_folder else input_folder
    loop = asyncio.get_event_loop()

    loop.run_until_complete(run())
    loop.close()
    logger.debug('Completed (%s - %s)', datetime.now(), start_time)
