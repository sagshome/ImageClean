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

sys.path.append('.')  # required to satisfy imports of backend
from backend.cleaner import FileCleaner  # pylint: disable=wrong-import-position import-error
from backend.image_clean import ImageClean  # pylint: disable=wrong-import-position import-error


APP_PATH: Path = Path(sys.argv[0])
APP_NAME: str = APP_PATH.stem

LOGGER_NAME: str = 'Cleaner'  # I am hard-coding this value. I call it from cmdline and UI which have diff app names
#  APP = ImageClean(LOGGER_NAME)  # Sets all default values


log_file = Path.home().joinpath(f'{LOGGER_NAME}.log')  # pylint: disable=invalid-name
if log_file.exists() and os.stat(log_file).st_size > 100000:  # pragma: no cover
    FileCleaner.rollover_file(log_file)

logger = logging.getLogger(LOGGER_NAME)  # pylint: disable=invalid-name

FH = logging.FileHandler(filename=log_file)
FH_FORMATTER = logging.Formatter('%(asctime)s %(levelname)s %(lineno)d:%(filename)s- %(message)s')
FH.setFormatter(FH_FORMATTER)
logger.addHandler(FH)  # pylint: disable=invalid-name

if os.getenv(f'{LOGGER_NAME.upper()}_DEBUG'):  # pragma: no cover
    # pylint: disable=invalid-name
    logger.setLevel(level=logging.DEBUG)
    oh = logging.StreamHandler()
    oh.setFormatter(FH_FORMATTER)
    logger.addHandler(oh)
else:
    logger.setLevel(level=logging.ERROR)


def short_help() -> str:
    """
    Build short help
    :return:
    """
    return f'{APP_NAME} -hcrdsv -i <import_folder> image_folder\n' \
           '\n\n-h: This help' \
           '\nThis application will reorganize image files into a folder structure that is human friendly' \
           '\nGo to https://github.com/sagshome/ImageClean/wiki for details'


def app_help(app: ImageClean) -> str:  # pragma: no cover
    """
    Build help text
    :param app:
    :return:
    """
    return f'{short_help()}' \
           '\n\n-c: Converted (HEIC) files to JPG files. The original HEIC files are saved into the' \
           f'"{app.migration_base}" folder' \
           '\n-r: Remove imported files. if the file is imported successfully,  the original file is removed' \
           '\n-d: Process Duplicates. look for and exact files in duplicate directories - and pick the best' \
           f'\n-s: Check for small files (save in "{app.small_base}" folder) - This WILL slow down processing' \
           '\n-v: Verbose,  blather on to the terminal' \
           '\n-i import folder - where we are importing from (default is just process image_folder)' \
           '\n\nimage folder - where to image files are saved'


async def run(app):  # pragma: no cover
    """
    This is needed to support async requirement of APP.run()
    :return:
    """
    await app.run()


def main(arg_strings=None) -> ImageClean:
    """
    Main program
    :param arg_strings: sys.argv
    :return: None
    """
    try:
        opts, args = getopt.getopt(arg_strings[1:], 'hcrsdvi:', [])
    except getopt.GetoptError:
        print(f'Invalid syntax: {sys.argv[1:]}\n\n')
        print(short_help())
        sys.exit(4)

    if len(args) != 1:
        print('\nimage folder is required.\n\n')
        print(short_help())
        sys.exit(2)

    options = {'output': Path(args[0]),
               'do_convert': False,
               'keep_originals': True,
               'verbose': False,
               'check_small': False,
               'check_duplicates': False}

    for opt, arg in opts:  # pragma: no cover
        if opt == '-h':
            print(app_help)
            sys.exit(2)
        elif opt == '-c':
            options['do_convert'] = True
        elif opt == '-r':
            options['keep_originals'] = False
        elif opt == '-s':
            options['check_small'] = True
        elif opt == '-d':
            options['check_duplicates'] = True
        elif opt == '-v':
            options['verbose'] = True
        elif opt == '-i':
            try:
                os.stat(arg)
            except FileNotFoundError:
                print(f'Import Folder: {arg} is not found.   Critical error \n\n {short_help()}')
                sys.exit(3)
            options['input'] = Path(arg)

    if 'input' not in options:
        options['input'] = options['output']

    return ImageClean(APP_NAME, restore=False, **options)


if __name__ == '__main__':  # pragma: no cover
    start_time = datetime.now()

    logger.debug('Starting (%s - %s)', datetime.now(), start_time)

    the_app = main(sys.argv)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run(the_app))
    loop.close()

    logger.debug('Completed (%s - %s)', datetime.now(), start_time)
