from backend.cleaner import CleanerBase, Folder, FileCleaner, ImageCleaner, PICTURE_FILES, MOVIE_FILES
from pathlib import Path
import os
import stat
from typing import Dict


class ImageClean:
    """

    """

    def __init__(self, base: str, init_base: bool = True):
        self.base = Path(base)
        self.base_files: Dict[str: Dict[str: FileCleaner | ImageCleaner]] = {}
        self.base_folders: Dict[str: str] = {}

        if init_base:
            _folder = Folder(self.base, self.base)
            self.base_folders[_folder.significant_path] = {'Folder': _folder, 'Files': {}}
            self.walktree(self.base, self.base, _folder.significant_path, self.base_folders, self.base_files)

    def walktree(self, top: Path, base: Path, folder_key: Path.as_posix, folders, files):
        """
           Read a directory
        """
        for f in os.listdir(top):
            this_obj = CleanerBase(top.joinpath(f))
            if this_obj.is_dir:
                this_folder = Folder(this_obj.path, base, stat=this_obj.stat)
                folder_key = this_folder.significant_path
                folders[folder_key] = {'Folder': this_folder, 'Files': {}}
                self.walktree(this_folder.path, base, folder_key, folders, files)
            elif this_obj.is_file:
                suffix = this_obj.path.suffix.lower()
                name = this_obj.path.name
                if suffix in PICTURE_FILES or suffix in MOVIE_FILES:
                    this_file = ImageCleaner(this_obj.path, stat=this_obj.stat)
                else:
                    this_file = FileCleaner(this_obj.path, stat=this_obj.stat)
                folders[folder_key]['Files'][this_file.path.name] = this_file

                if this_file.path.name not in files:  # A new filename has been found
                    files[this_file.path.name] = {this_file.stat.st_size: {'best_fit': folder_key, 'all_folders': [folder_key,]}}
                else:  # Existing filename exists
                    if this_file.stat.st_size not in files[this_file.path.name]:  # A new size of filename has been found
                        files[this_file.path.name][this_file.stat.st_size] = {'best_fit': folder_key, 'all_folders': [folder_key,]}
                    else: # Existing duplicate size (good enough for now) was found,  compare directory score to existing best
                        existing_best_fit = files[this_file.path.name][this_file.stat.st_size]['best_fit']  # current best fit index into folders
                        if folders[existing_best_fit]['Folder'].score < folders[folder_key]['Folder'].score:
                            files[this_file.path.name][this_file.stat.st_size]['best_fit'] = folder_key
                    files[this_file.path.name][this_file.stat.st_size]['all_folders'].append(folder_key)
            else:
                # Unknown file type, print a message
                print('Skipping %s' % this_obj)

    #@classmethod
def audit(folders, files):
    """

    :param folders:
    :param files:
    :return:
    """
    for file in files:
        for size in files[file].keys():
            if len(files[file][size]) > 1:
                for entry in files[file][size]['all_folders']:
                    if entry != files[file][size]['best_fit']:
                        print(f'duplicate: {entry}: {file} - BestFit:{folders[files[file][size]['best_fit']]['Folder'].significant_path}')


def compare(base, new):
    for file in new:
        if file in base:
            for size in new[file].keys():
                if size not in base[file]:
                    print(f'Import SIZE {file} to {new[file][size]['best_fit']}')
        else:
            for size in new[file].keys():
                print(f'Import NEW {file} to {new[file][size]['best_fit']}')



