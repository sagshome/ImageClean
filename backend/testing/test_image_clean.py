"""
Test Cases for the Image Clean classes
"""
# pylint: disable=duplicate-code
# pylint: disable=too-many-lines
# pylint: disable=line-too-long
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
import os
import platform
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pytest

# xpylint: disable=import-error
from backend.cleaner import CleanerBase, ImageCleaner
from backend.image_clean import ImageClean
from Utilities.test_utilities import create_file, create_image_file, count_files
from Utilities.test_utilities import DIR_SPEC, YEAR_SPEC, DATE_SPEC, DEFAULT_NAME


class ActualScenarioTest(unittest.IsolatedAsyncioTestCase):
    """
    Create real world scenario's for testing.   This is perhaps not unit tests but system tests

    These tests cover all the duplicate scenarios


    """
    # pylint: disable=too-many-public-methods, too-many-instance-attributes
    def tearDown(self):
        self.temp_base.cleanup()
        CleanerBase.clear_caches()
        super().tearDown()

    def setUp(self):
        super().setUp()
        print(self.__class__.__name__, self._testMethodName)

        self.app_name = 'test_instance'

        # Make basic folders
        self.temp_base = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.output_folder = Path(self.temp_base.name).joinpath('Output')
        self.input_folder = Path(self.temp_base.name).joinpath('Input')

        os.mkdir(self.output_folder)
        os.mkdir(self.input_folder)

    @patch('pathlib.Path.home')  # strange date extended base on import
    async def test_use_case_9_a(self, home):
        """
        Found in test runs
        Input <in>/2008_04_12_02/151-5181_IMG.JPG

        Output <out>/2008/04/12/02/151-5181_IMG.JPG

        On reimport out to out it moved to the correct possition:
        Output <out>/2008/04/12/151-5181_IMG.JPG
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)
        input_file = create_image_file(self.input_folder.joinpath('2008_04_12_02'), DATE_SPEC)
        output = self.output_folder.joinpath('2008').joinpath('04').joinpath('12').joinpath(DEFAULT_NAME)

        self.assertTrue(input_file.exists())
        self.assertFalse(output.exists())

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=False)
        await cleaner.run()
        self.assertFalse(input_file.exists())
        self.assertTrue(output.exists())

    @patch('pathlib.Path.home')  # Move a file using internal date stamp
    async def test_use_case_9(self, home):
        """
        99% of input files.
        Input:
        <input>/dated.jpg

        Output:
        <output/YYYY/mm/dd/dated.jpg

        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)
        input_file = create_image_file(self.input_folder, DATE_SPEC)
        output = self.output_folder.joinpath(DIR_SPEC).joinpath(DEFAULT_NAME)

        self.assertTrue(input_file.exists())
        self.assertFalse(output.exists())

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=False)
        await cleaner.run()
        self.assertFalse(input_file.exists())
        self.assertTrue(output.exists())

    @patch('pathlib.Path.home')  # Input and Output are the same (dated directories)
    async def test_use_case_2(self, home):
        """
        A standard input is re-attempted
        Input:
        <output>/YYYY/MM/DD/dated.jpg

        Output:
        <output>/YYYY/MM/DD/dated.jpg
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)
        input_file = create_image_file(self.output_folder.joinpath(DIR_SPEC), DATE_SPEC)
        output = self.output_folder.joinpath(DIR_SPEC).joinpath(DEFAULT_NAME)

        self.assertTrue(input_file.exists())
        self.assertTrue(output.exists())

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.input_folder,
                             verbose=True, keep_originals=False)
        await cleaner.run()
        self.assertTrue(input_file.exists())
        self.assertTrue(output.exists())

    @patch('pathlib.Path.home')  # Input and Output are the same (custom directories)
    async def test_use_case_2b(self, home):
        """
        A standard input is re-attempted
        Input:
        <output>/YYYY/MM/DD/dated.jpg

        Output:
        <output>/YYYY/MM/DD/dated.jpg
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)
        input_file = create_image_file(self.output_folder.joinpath(YEAR_SPEC).joinpath('custom'), DATE_SPEC)

        self.assertTrue(input_file.exists())

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.input_folder,
                             verbose=True, keep_originals=False)
        await cleaner.run()
        self.assertTrue(input_file.exists())

    @patch('pathlib.Path.home')  # Input Folder == Child of Output Folder
    async def test_use_case_3(self, home):
        """
        Use Case 3)
            Input Folder == Child of Output Folder - Same as Use Case 1 but bear in mind we may try and import in place

        Input:
        <output>/foobar
              dated.jpg

        Output:
        <output/YYYY/foobar/dated.jpg

        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)
        input_file = create_image_file(self.output_folder.joinpath('foobar'), DATE_SPEC)
        output = self.output_folder.joinpath(YEAR_SPEC).joinpath('foobar').joinpath(DEFAULT_NAME)

        self.assertTrue(input_file.exists())
        self.assertFalse(output.exists())

        cleaner = ImageClean(self.app_name, input=self.output_folder.joinpath('foobar'), output=self.output_folder,
                             verbose=False, keep_originals=False)
        await cleaner.run()
        self.assertFalse(input_file.exists())
        self.assertTrue(output.exists())

    @patch('pathlib.Path.home')
    async def test_use_case_4(self, home):
        """
        Use Case 4)
            Input Folder == Parent of Output Folder

        Input:
        <output>/dated.jpg

        Output:
        <output>/<new_path>
              /YYYY/foobar/dated.jpg

        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)
        input_file = create_image_file(self.output_folder, DATE_SPEC)
        output = self.output_folder.joinpath('newpath').joinpath(DIR_SPEC).joinpath(DEFAULT_NAME)
        os.mkdir(self.output_folder.joinpath('newpath'))

        self.assertTrue(input_file.exists())
        self.assertFalse(output.exists())

        cleaner = ImageClean(self.app_name, input=self.output_folder, output=self.output_folder.joinpath('newpath'),
                             verbose=False, keep_originals=False)
        await cleaner.run()
        self.assertFalse(input_file.exists())
        self.assertTrue(output.exists())

    @patch('pathlib.Path.home')
    async def test_use_case_5(self, home):
        """
        Use Case 5) - Support small files
        Input:
        <input>/small_dated.jpg

        Output:
        <output>/<small_folder/>
              /YYYY/MM/DD/dated.jpg

        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=False, check_small=True)

        input_file = create_image_file(self.input_folder, DATE_SPEC, small=True)
        output_file = self.output_folder.joinpath(cleaner.small_base).joinpath(DIR_SPEC).joinpath(DEFAULT_NAME)

        self.assertTrue(input_file.exists())
        self.assertFalse(output_file.exists())

        await cleaner.run()
        self.assertFalse(input_file.exists())
        self.assertTrue(output_file.exists())

    @patch('pathlib.Path.home')
    async def test_use_case_7(self, home):
        """
        Use Case 7) - Ignore non-image files
        Input:
        <input>/file.txt

        Output:
        <input>/file.txt

        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=False, check_small=True)

        input_file = create_file(self.input_folder.joinpath('file.txt'))

        self.assertTrue(input_file.exists())

        await cleaner.run()
        self.assertTrue(input_file.exists())

    @patch('pathlib.Path.home')
    async def test_use_case_8(self, home):
        """
        Use Case 8) - Archive movie files
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=False, check_small=True)

        input_file = create_file(self.input_folder.joinpath('file.mov'))
        output_file = self.output_folder.joinpath(cleaner.movies_base).joinpath(cleaner.no_date_base).\
            joinpath('file.mov')

        self.assertTrue(input_file.exists())
        self.assertFalse(output_file.exists())

        await cleaner.run()
        self.assertFalse(input_file.exists())
        self.assertTrue(output_file.exists())

    @patch('pathlib.Path.home')
    async def test_use_case_8b(self, home):
        """
        Use Case 8) - Archive movie files (input had a date)
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=False, check_small=True)

        input_file = create_file(self.input_folder.joinpath('2022').joinpath('file.mov'))
        output_file = self.output_folder.joinpath(cleaner.movies_base).joinpath('2022').joinpath('file.mov')

        self.assertTrue(input_file.exists())
        self.assertFalse(output_file.exists())

        await cleaner.run()
        self.assertFalse(input_file.exists())
        self.assertTrue(output_file.exists())

    @patch('pathlib.Path.home')  # If a dated image is in no_date folder reimport should move it
    async def test_use_case_8c(self, home):
        """
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)

        cleaner = ImageClean(self.app_name, input=self.output_folder, output=self.output_folder,
                             verbose=False, keep_originals=False, check_small=True)

        input_file = create_image_file(self.output_folder.joinpath(cleaner.no_date_base), DATE_SPEC)
        output_file = self.output_folder.joinpath(DIR_SPEC).joinpath(DEFAULT_NAME)

        self.assertTrue(input_file.exists())
        self.assertFalse(output_file.exists())

        await cleaner.run()
        self.assertFalse(input_file.exists())
        self.assertTrue(output_file.exists())

    @patch('pathlib.Path.home')  # Input image has a folder date,  write that in when moving
    async def test_use_case_8d(self, home):
        """
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=False, check_small=False)

        input_file = create_image_file(self.input_folder.joinpath(DIR_SPEC), None)
        test1 = ImageCleaner(input_file)
        self.assertIsNone(test1.date)

        await cleaner.run()
        self.assertFalse(input_file.exists())
        output_file = self.output_folder.joinpath(DIR_SPEC).joinpath(DEFAULT_NAME)
        self.assertTrue(output_file.exists)
        test2 = ImageCleaner(output_file)
        self.assertEqual(test2.date, DATE_SPEC, "Date should now exist")

    @patch('pathlib.Path.home')  # Input image has a date in filename,  write that in when moving
    async def test_use_case_8e(self, home):
        """
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=False, check_small=False)

        input_file = create_image_file(self.input_folder.joinpath(DIR_SPEC).joinpath('19610927_121212_IMG.jpg'), None)
        test1 = ImageCleaner(input_file)
        self.assertEqual(test1.date, DATE_SPEC, "Date should now exist")
        self.assertFalse(test1._metadate, "Date was derived")  # pylint: disable=protected-access

        await cleaner.run()
        self.assertFalse(input_file.exists())
        output_file = self.output_folder.joinpath(DIR_SPEC).joinpath('19610927_121212_IMG.jpg')
        self.assertTrue(output_file.exists)
        test2 = ImageCleaner(output_file)
        self.assertEqual(test2.date, DATE_SPEC, "Date should exist")
        self.assertTrue(test2._metadate, "Date was internal")  # pylint: disable=protected-access

    @patch('pathlib.Path.home')  # Input image with description and no date
    async def test_use_case_10a(self, home):
        """
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=False, check_small=False)

        input_file = create_image_file(self.input_folder.joinpath('custom'), None)

        await cleaner.run()
        self.assertFalse(input_file.exists())
        self.assertTrue(self.output_folder.
                        joinpath(cleaner.no_date_base).joinpath('custom').joinpath(DEFAULT_NAME).exists())

    @patch('pathlib.Path.home')  # Input image with description full directory date and no date
    async def test_use_case_10b(self, home):
        """
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=False, check_small=False)

        input_file = create_image_file(self.input_folder.joinpath(DIR_SPEC).joinpath('custom'), None)

        await cleaner.run()
        self.assertFalse(input_file.exists())
        self.assertTrue(self.output_folder.joinpath(YEAR_SPEC).joinpath('09-27 custom').joinpath(DEFAULT_NAME).exists())

    @patch('pathlib.Path.home')  # To different images going to the same place
    async def test_different_file_exists(self, home):
        """
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=False)

        input_file = create_image_file(self.input_folder, DATE_SPEC, text='foo')
        existing_file = create_image_file(self.output_folder.joinpath(DIR_SPEC), DATE_SPEC, text='bar')

        self.assertTrue(existing_file.exists())
        self.assertEqual(count_files(self.output_folder.joinpath(DIR_SPEC)), 1)

        await cleaner.run()
        self.assertFalse(input_file.exists())
        self.assertTrue(existing_file.exists())
        self.assertEqual(count_files(self.output_folder.joinpath(DIR_SPEC)), 2)

    @patch('pathlib.Path.home')  # custom version of different file exists
    async def test_different_file_exists2(self, home):
        """
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=False)

        input_file = create_image_file(self.input_folder, DATE_SPEC, text='foo')
        existing_file = create_image_file(self.output_folder.joinpath(YEAR_SPEC).joinpath('custom'),
                                          DATE_SPEC, text='bar')

        self.assertTrue(existing_file.exists())
        self.assertEqual(count_files(self.output_folder), 1)

        await cleaner.run()
        self.assertFalse(input_file.exists())
        self.assertTrue(existing_file.exists())
        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath(DEFAULT_NAME).exists())

        self.assertEqual(count_files(self.output_folder), 2)

    @patch('pathlib.Path.home')  # custom version of same file exists
    async def test_different_file_exists3(self, home):
        """
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=False)

        input_file = create_image_file(self.input_folder, DATE_SPEC, text='foo')
        existing_file = create_image_file(self.output_folder.joinpath(YEAR_SPEC).joinpath('custom'),
                                          DATE_SPEC, text='foo')
        duplicate_file = self.output_folder.joinpath(cleaner.duplicate_base).\
            joinpath(YEAR_SPEC).joinpath('custom').joinpath(DEFAULT_NAME)
        self.assertTrue(existing_file.exists())
        self.assertFalse(duplicate_file.exists())
        self.assertEqual(count_files(self.output_folder), 1)

        await cleaner.run()
        self.assertFalse(input_file.exists())
        self.assertTrue(existing_file.exists())
        self.assertTrue(duplicate_file.exists())
        self.assertEqual(count_files(self.output_folder), 2)

    @patch('pathlib.Path.home')  # Date version of a custom folder exists
    async def test_different_file_exists4(self, home):
        """
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)
        cleaner = ImageClean(self.app_name, input=self.output_folder, output=self.output_folder,
                             verbose=False, keep_originals=False)

        create_image_file(self.output_folder.joinpath(DIR_SPEC), DATE_SPEC)
        create_image_file(self.output_folder.joinpath(YEAR_SPEC).joinpath('custom'), DATE_SPEC)
        self.assertEqual(count_files(self.output_folder), 2)

        await cleaner.run()
        self.assertTrue(self.output_folder.joinpath(cleaner.duplicate_base).
                        joinpath(YEAR_SPEC).joinpath('custom').joinpath(DEFAULT_NAME).exists())
        self.assertEqual(count_files(self.output_folder), 2)

    @patch('pathlib.Path.home')  # Two a custom folder exists
    async def test_different_file_exists5(self, home):
        """
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)
        cleaner = ImageClean(self.app_name, input=self.output_folder, output=self.output_folder,
                             verbose=False, keep_originals=False)
        input_file1 = create_image_file(self.output_folder.joinpath(YEAR_SPEC).joinpath('custom'), DATE_SPEC)
        input_file2 = create_image_file(self.output_folder.joinpath(YEAR_SPEC).joinpath('custom2'), DATE_SPEC)
        self.assertEqual(count_files(self.output_folder), 2)

        await cleaner.run()
        self.assertTrue(input_file1.exists())
        self.assertTrue(input_file2.exists())

        self.assertEqual(count_files(self.output_folder), 2)

    @patch('pathlib.Path.home')  # Two a custom folder exists
    async def test_different_file_exists6(self, home):
        """
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=True, keep_originals=False)
        create_image_file(self.input_folder.joinpath(YEAR_SPEC).joinpath('02'). joinpath('custom'),
                                        DATE_SPEC)
        input_file2 = create_image_file(self.output_folder.joinpath(YEAR_SPEC).joinpath('custom2'), DATE_SPEC)
        self.assertEqual(count_files(self.output_folder), 1)

        await cleaner.run()
        self.assertTrue(self.output_folder.
                        joinpath(YEAR_SPEC).joinpath('02 custom').joinpath(DEFAULT_NAME).exists())
        self.assertTrue(input_file2.exists())

        self.assertEqual(count_files(self.output_folder), 2)

    @patch('pathlib.Path.home')  # Two a custom folder exists
    async def test_different_file_exists7(self, home):
        """
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=True)
        input_file1 = create_image_file(self.input_folder.joinpath(YEAR_SPEC).joinpath('custom'), DATE_SPEC)
        input_file2 = create_image_file(self.output_folder.joinpath(DIR_SPEC), DATE_SPEC)
        self.assertEqual(count_files(self.output_folder), 1)

        await cleaner.run()
        self.assertTrue(self.output_folder.joinpath(YEAR_SPEC).joinpath('custom').joinpath(DEFAULT_NAME).exists())
        self.assertTrue(self.output_folder.
                        joinpath(cleaner.duplicate_base).joinpath(DIR_SPEC).joinpath(DEFAULT_NAME).exists())
        self.assertFalse(input_file2.exists())
        self.assertTrue(input_file1.exists())
        self.assertEqual(count_files(self.output_folder), 2)

    @patch('pathlib.Path.home')  # Two a custom folder exists
    async def test_movies(self, home):
        """
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=False)
        create_file(self.input_folder.joinpath('test.mov'))
        create_image_file(self.input_folder.joinpath('test.jpg'), DATE_SPEC)
        create_file(self.input_folder.joinpath(DIR_SPEC).joinpath('test2.mov'))

        self.assertEqual(count_files(self.output_folder), 0)

        await cleaner.run()
        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath('test.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(cleaner.movies_base).
                        joinpath(cleaner.no_date_base).joinpath('test.mov').exists())
        self.assertTrue(self.output_folder.joinpath(cleaner.movies_base).
                        joinpath(DIR_SPEC).joinpath('test2.mov').exists())
        self.assertEqual(count_files(self.input_folder), 0)
        self.assertEqual(count_files(self.output_folder), 3)


class InitTest(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        super().setUp()
        print(self.__class__.__name__, self._testMethodName)

        self.tempdir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with

    def tearDown(self):
        self.tempdir.cleanup()
        super().tearDown()

    @patch('pathlib.Path.home')
    async def test_init(self, home):
        """
        Basic test for initialized values
        :return:
        """
        home.return_value = Path(self.tempdir.name)
        app = ImageClean('test_app')
        self.assertEqual(app.app_name, 'test_app', "Failed to set the app name")
        self.assertIsNotNone(app.conf_file, f'Config file {app.conf_file} is not set')
        self.assertEqual(app.input_folder, Path.home())
        self.assertEqual(app.input_folder, app.output_folder)
        self.assertFalse(app.verbose, "Verbose is not True")
        #self.assertTrue(app.do_convert, "Conversion are not True")
        self.assertFalse(app.force_keep)
        self.assertTrue(app.keep_original_files, "Keep original default is not True")
        self.assertEqual(app.progress, 0, "Progress has not been initialized")
        app.teardown()

    @patch('pathlib.Path.home')
    async def test_run_path(self, home):
        home.return_value = Path(self.tempdir.name)

        expected_run_path = Path(Path.home().joinpath('.test_app_init_test'))
        app = ImageClean('test_app_init_test')
        app.verbose = False
        self.assertTrue(expected_run_path.exists())
        app.teardown()

    @patch('pathlib.Path.home')
    async def test_save_and_restore(self, home):   # pylint: disable=too-many-statements

        home.return_value = Path(self.tempdir.name)

        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            app = ImageClean('test_app', restore=True)
            error_value = 'DEBUG:Cleaner:Restore attempt of'
            self.assertTrue(logs.output[len(logs.output) - 1].startswith(error_value), 'Restore Fails')
            # default value
            self.assertEqual(app.app_name, 'test_app', "Failed to set the app name")
            self.assertIsNotNone(app.conf_file, f'Config file {app.conf_file} is not set')
            self.assertEqual(app.input_folder, Path.home())
            self.assertEqual(app.input_folder, app.output_folder)
            self.assertFalse(app.verbose, "Verbose is not True")
            # self.assertTrue(app.do_convert, "Conversion are not True")
            self.assertTrue(app.keep_original_files, "Keep original default is not True")

            app.input_folder = Path('/input')
            app.output_folder = Path('/output')
            app.verbose = True
            app.do_convert = False
            app.keep_original_files = False

            app.save_config()
            app.teardown()

        app = ImageClean('test_app', restore=True)
        self.assertEqual(app.input_folder, Path('/input'))
        self.assertEqual(app.output_folder, Path('/output'))
        self.assertTrue(app.verbose, "Verbose is not True")
        self.assertFalse(app.do_convert, "Conversion are not True")
        self.assertFalse(app.keep_original_files, "Keep original default is not True")
        app.teardown()

    @patch('pathlib.Path.home')
    async def test_prepare(self, home):
        home.return_value = Path(self.tempdir.name)
        if platform.system() not in ['Windows', 'win32']:  # pragma: no cover
            output_folder = Path(self.tempdir.name).joinpath('output')
            input_folder = Path(self.tempdir.name).joinpath('input')

            os.mkdir(output_folder)
            os.mkdir(input_folder)

            app = ImageClean('test_app')
            app.output_folder = output_folder
            app.input_folder = input_folder
            app.verbose = False

            os.chmod(output_folder, mode=stat.S_IREAD)  # set to R/O
            with pytest.raises(AssertionError):  # Must assert with R/O output folder
                await app.run()

            os.chmod(output_folder, mode=stat.S_IRWXU)  # Rest output
            os.chmod(input_folder, mode=stat.S_IREAD)  # Set input to R/O

            await app.run()
            self.assertTrue(app.force_keep, 'Force Keep is set')

            app.input_folder = app.output_folder

            await app.run()

            # Auto Cleanup in action
            self.assertFalse(output_folder.joinpath(app.duplicate_base).exists(), 'Duplicate path does not exist')
            self.assertFalse(output_folder.joinpath(app.migration_base).exists(), 'Migrate path does not exist')
            self.assertFalse(output_folder.joinpath(app.movies_base).exists(), 'Movie path does not exist')
            self.assertFalse(output_folder.joinpath(app.no_date_base).exists(), 'No_Date path does not exist')
            self.assertFalse(output_folder.joinpath(app.small_base).exists(), 'Small path does not exist')


class EdgeCaseTest(unittest.IsolatedAsyncioTestCase):  # pylint: disable=too-many-instance-attributes
    """
    These are test cases not covered in Actual Scenarios or Initialization
    """

    def tearDown(self):
        self.temp_base.cleanup()
        CleanerBase.clear_caches()
        super().tearDown()

    def setUp(self):
        super().setUp()
        print(self.__class__.__name__, self._testMethodName)
        self.app_name = 'test_instance'

        # Make basic folders
        self.temp_base = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.output_folder = Path(self.temp_base.name).joinpath('Output')
        self.input_folder = Path(self.temp_base.name).joinpath('Input')

        os.mkdir(self.output_folder)
        os.mkdir(self.input_folder)

    @patch('pathlib.Path.home')
    async def test_read_only_input_forces_force_ro(self, home):
        if platform.system() not in ['Windows', 'win32']:  # pragma: no cover
            home.return_value = Path(self.temp_base.name)
            orig = create_image_file(self.input_folder, None)
            os.chmod(self.input_folder, mode=(stat.S_IREAD | stat.S_IEXEC))  # Set input to R/O
            cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
            cleaner.keep_original_files = False
            cleaner.verbose = False
            await cleaner.run()
            self.assertTrue(orig.exists())

    @patch('builtins.print')
    @patch('pathlib.Path.home')
    async def test_invalid(self, home, my_print):
        home.return_value = Path(self.temp_base.name)
        create_file(self.input_folder.joinpath('text.jpg'), empty=True)
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder, verbose=False)
        cleaner.verbose = False
        await cleaner.run()
        my_print.assert_not_called()

        cleaner.verbose = True
        await cleaner.run()
        my_print.assert_called()


    @patch('backend.image_clean.WARNING_FOLDER_SIZE', 2)
    @patch('builtins.print')
    @patch('pathlib.Path.home')
    async def test_audit_folders(self, home, my_print):
        home.return_value = Path(self.temp_base.name)
        create_image_file(self.output_folder.joinpath(DIR_SPEC).joinpath('one.jpg'), DATE_SPEC)
        create_image_file(self.output_folder.joinpath(DIR_SPEC).joinpath('two.jpg'), DATE_SPEC)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=True, keep_originals=False)
        await cleaner.run()
        found = False
        for call_item in my_print.call_args_list:
            if call_item.args[0].strip().startswith('VERY large folder'):
                found = True  # pragma: no cover
        self.assertFalse(found, 'Very large folder should not be found')

        CleanerBase.clear_caches()
        create_image_file(self.output_folder.joinpath(DIR_SPEC).joinpath('three.jpg'), DATE_SPEC)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=True, keep_originals=True)
        await cleaner.run()
        found = False
        for call_item in my_print.call_args_list:  # pragma: no cover
            if call_item.args[0].strip().startswith('VERY large folder'):
                found = True
                break
        self.assertTrue(found, 'Very large folder should be found')

    @patch('pathlib.Path.home')
    async def test_audit_folders_cleanup(self, home):
        home.return_value = Path(self.temp_base.name)
        create_image_file(self.input_folder.joinpath(DIR_SPEC).joinpath('one.jpg'), DATE_SPEC)
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=True, keep_originals=False)
        await cleaner.run()
        self.assertFalse(self.input_folder.joinpath(DIR_SPEC).exists(), 'Cleanup removes sub-folder')

        CleanerBase.clear_caches()

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=True, keep_originals=True)
        await cleaner.run()
        self.assertFalse(self.input_folder.joinpath(DIR_SPEC).exists(), 'Cleanup removes sub-folder')

    @patch('pathlib.Path.home')
    async def test_remove_test(self, home):
        home.return_value = Path(self.temp_base.name)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder, verbose=True)

        input_object = ImageCleaner(create_image_file(self.input_folder, DATE_SPEC))
        output_object = ImageCleaner(create_image_file(self.output_folder.joinpath(DIR_SPEC), DATE_SPEC))

        cleaner.keep_original_files = False
        cleaner.force_keep = False
        self.assertTrue(cleaner.remove_file(input_object))
        self.assertTrue(cleaner.remove_file(output_object))

        cleaner.keep_original_files = True
        self.assertFalse(cleaner.remove_file(input_object))
        self.assertTrue(cleaner.remove_file(output_object))

        cleaner.keep_original_files = False
        cleaner.force_keep = True
        self.assertFalse(cleaner.remove_file(input_object))
        self.assertTrue(cleaner.remove_file(output_object))

        cleaner.teardown()

if __name__ == '__main__':  # pragma: no cover
    unittest.main()
