"""
Command line call for Cleaning

Goals.
1. Convert HEIC files to JPG  - Only if requested and only if on Linux systems (macs support them,  windows can't process them)
2. Any root folder file should move into a dated directory YYYY/MM
# 3. SubDirectories,  with a 'dated parent' should be imported with that date.  2002-02-02 Picnic / swimming / img01.jpg
3. Any file without date info and not in a dated parent,  moves into - no date folder
5. no date folder is always processed incase I set the date.
4. garbage is ignored
5. Clean up duplicates
"""
import argparse
import asyncio

import logging
import os
import sys
from datetime import datetime

sys.path.append('.')  # required to satisfy imports of backend

from CleanerBase import APPLICATION, config_dir, user_dir, log_dir
from StandardFile import StandardFile
from cleaner_app import CleanerApp  # DESCRIPTION, EXTRA_HELP


DESCRIPTION = 'This application will reorganize image/data files into a folder structure that is human friendly'
EXTRA_HELP = 'Go to https://github.com/sagshome/ImageClean/wiki for details'

run_path = user_dir()
conf_file = config_dir().joinpath('config.pickle')
log_file = log_dir().joinpath(f'{APPLICATION}.log')

if log_file.exists() and os.stat(log_file).st_size > 100000:
    StandardFile.rollover_file(log_file, max_copies=5)

logger = logging.getLogger(APPLICATION)

FH = logging.FileHandler(filename=log_file)
FH_FORMATTER = logging.Formatter('%(asctime)s %(levelname)s %(lineno)d:%(filename)s- %(message)s')
FH.setFormatter(FH_FORMATTER)
logger.addHandler(FH)

if os.getenv(f'{APPLICATION.upper()}_DEBUG'):
    logger.setLevel(level=logging.DEBUG)
    oh = logging.StreamHandler()
    oh.setFormatter(FH_FORMATTER)
    logger.addHandler(oh)
else:
    logger.setLevel(level=logging.ERROR)


async def run(app):  # pragma: no cover
    """
    This is needed to support async requirement of APP.run()
    :return:
    """
    await app.run()


def main() -> CleanerApp:
    """
    Main program
    :return: None
    """
    cmdline_parser = argparse.ArgumentParser(
        prog=APPLICATION,
        description=DESCRIPTION,
        epilog=EXTRA_HELP)

    cmdline_parser.add_argument('input_folder')
    cmdline_parser.add_argument('output_folder')
    cmdline_parser.add_argument('-v', '--verbose', action='store_true', help='Send a lot of output to the screen')
    cmdline_parser.add_argument('-r', '--remove', action='store_true', help=' files after the import (even if skipped)')
    cmdline_parser.add_argument('-c', '--convert', action='store_true', help='Change HEIC files to JPEG format')

    cmdline_parser.add_argument('-s', '--small', action='store_true', help="Store very small images, in a directory named 'small'")
    cmdline_parser.add_argument('-d', '--data', action='store_true',
                                help="Also process files that are not images,  they will be stored under 'output_folder' with the prefix 'data'")
    cmdline_parser.add_argument('-f', '--fix_date', action='store_true',
                                help='When processing an image without an internal datestamp,  set it based on file datestamp')
    cmdline_parser.add_argument('-m', '--match_date', action='store_true',
                                help="When processing an image, set the file datestamp based on the internal image datestamp")

    args = cmdline_parser.parse_args()
    args_dict = vars(args)
    args_dict['restore'] = False
    logger.debug('%s' % args_dict)
    ic = CleanerApp()
    return CleanerApp(**args_dict)


if __name__ == '__main__':  # pragma: no cover
    start_time = datetime.now()

    logger.debug('Starting (%s - %s)', datetime.now(), start_time)

    the_app = main()
    if not the_app.setup():
        exit(1)

    # Start it up.
    the_app.print('Starting Imports.')
    asyncio.run(the_app.import_from_cache())
    the_app.teardown()
    logger.debug('Completed (%s - %s)', datetime.now(), start_time)
