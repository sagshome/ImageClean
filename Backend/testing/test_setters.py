import os
import sys
import unittest

from pathlib import Path
from Backend.Cleaner import Cleaner, ImageClean, file_cleaner
sys.path.append(f'{Path.home()}'.joinpath('ImageClean'))  # I got to figure out this hack,
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))


class CleanerUtilsTest(unittest.TestCase):

    def test_objects(self):
        for image_type in ['.JPG', '.HEIC', '.AVI', '.MP4', '.THM', '.RTF', '.PNG', '.JPEG', '.MOV', '.TIFF']:
            my_object = file_cleaner(Path(f'/fake/foo.{image_type}'), None)
            self.assertEqual('ImageCleaner', my_object.__class__.__name__,
                             f'Expected ImageCleaner Object - got {my_object.__class__.__name__}')
        my_object = file_cleaner(Path(f'/fake/foo.text'), None)
        self.assertEqual('FileCleaner', my_object.__class__.__name__,
                         f'Expected FileCleaner Object - got {my_object.__class__.__name__}')
        my_object = file_cleaner(Path.home(), None)
        self.assertEqual('FolderCleaner', my_object.__class__.__name__,
                         f'Expected FolderCleaner Object - got {my_object.__class__.__name__}')


class CleanerDefaultCompareTest(unittest.TestCase):

    def setUp(self):
        super(CleanerDefaultCompareTest, self).setUp()
        self.file1 = Cleaner(Path('/fake/a.file'), None)
        self.file2 = Cleaner(Path('/fake/b.file'), None)

    def test_compare(self):
        with self.assertRaises(NotImplementedError):
            res = self.file1 == self.file2
        with self.assertRaises(NotImplementedError):
            res = self.file1 > self.file2
        with self.assertRaises(NotImplementedError):
            res = self.file1 < self.file2
        with self.assertRaises(NotImplementedError):
            res = self.file1 != self.file2


class ImageCleanTest(unittest.TestCase):

    def setUp(self):
        self.app = ImageClean('test_app')

    def test_init(self):
        """
        Basic test for initialized values
        :return:
        """
        expected_run_path = Path(Path.home().joinpath('.test_app'))
        self.assertEqual(self.app.app_name, 'test_app', "Failed to set the app name")
        self.assertEqual(self.app.run_path, expected_run_path,
                         f"Run Path {self.app.run_path} is not set to {expected_run_path}")
        self.assertIsNotNone(self.app.conf_file, f'Config file {self.app.conf_file} is not set')
        self.assertEqual(self.app.input_folder, Path.home())
        self.assertEqual(self.app.input_folder, self.app.output_folder)
        self.assertTrue(self.app.verbose, "Verbose is not True")
        self.assertTrue(self.app.do_convert, "Conversion are not True")
        self.assertFalse(self.app.recreate, "Recreate is not false")
        self.assertTrue(self.app.do_convert)
        self.assertFalse(self.app.recreate)
        self.assertFalse(self.app.force_keep)
        self.assertFalse(self.app.keep_duplicates)
        self.assertFalse(self.app.keep_movie_clips)
        self.assertFalse(self.app.process_all_files)
        self.assertFalse(self.app.keep_converted_files)
        self.assertTrue(self.app.keep_original_files, "Keep original default is not True")
        self.assertListEqual(self.app.ignore_folders, [], "Ignore folders list is not empty")
        self.assertListEqual(self.app.bad_parents, [], "Name ignore list is not empty")
        self.assertEqual(self.app.progress, 0, "Progress has not been initialized")


if __name__ == '__main__':  # pragma: no cover
    unittest.main()