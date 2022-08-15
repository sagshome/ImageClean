# Driver program for restructuring image files.
import getopt
import logging
import os
import sys

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

from Backend.Cleaner import FileCleaner, ImageCleaner, FolderCleaner, file_cleaner, ImageClean


app_path = Path(sys.argv[0])
app_name = app_path.name[:len(app_path.name) - len(app_path.suffix)]

app = ImageClean(app_name)  # Sets all default values

app_help = f'{app_name} -hdmsaruPV -i <ignore_folder>... -n <non_description_folder>... -o <output> input_folder\n' \
           f'Used to clean up directories.' \
           f'\n\n-h: This help' \
           f'\n-d: Save duplicate files into {app.duplicate_path_base}' \
           f'\n-m: Save movie-clips that are also images (iphone live picture movies) into {app.movie_path_base}' \
           f'\n-c: Save original images that were successfully converted (HEIC) to JPG into {app.converted_path_base}'  \
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
            app.recreate = True
        elif opt == '-d':
            app.keep_duplicates = True
        elif opt == '-m':
            app.keep_movie_clips = True
        elif opt == '-a':
            app.process_all_files = True
        elif opt == '-c':
            app.keep_converted_files = True
        elif opt == '-s':
            app.keep_original_files = True
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
