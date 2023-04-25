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

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

# pylint: disable=import-error
from backend.cleaner import CleanerBase, FolderCleaner, ImageCleaner
from backend.image_clean import ImageClean
from Utilities.test_utilities import create_file, create_image_file, count_files, copy_file
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
        self.my_location = Path(os.path.dirname(__file__))
        self.app_name = 'test_instance'

        # Make basic folders
        self.temp_base = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.output_folder = Path(self.temp_base.name).joinpath('Output')
        self.input_folder = Path(self.temp_base.name).joinpath('Input')
        self.other_folder = self.input_folder.joinpath('custom')

        os.mkdir(self.output_folder)
        os.mkdir(self.input_folder)
        os.mkdir(self.other_folder)

        self.heic_file = self.my_location.joinpath('data').joinpath('heic_image.HEIC')

        # print(f'{str(self)} - {self.temp_base.name}')

    @patch('pathlib.Path.home')
    async def test_multiple_custom1(self, home):
        """
        Input:
        <input>/custom1/custom2/dated.jpg

        Output:
        <output/YYYY/custom1/custom2/dated.jpg

        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)
        input_file = create_image_file(self.input_folder.joinpath('custom1').joinpath('custom2'), DATE_SPEC)
        output = self.output_folder.joinpath(YEAR_SPEC).joinpath('custom1').joinpath('custom2').joinpath(DEFAULT_NAME)

        self.assertTrue(input_file.exists())
        self.assertFalse(output.exists())

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=False)
        await cleaner.run()
        self.assertFalse(input_file.exists())
        self.assertTrue(output.exists())

    @patch('pathlib.Path.home')
    async def test_custom2(self, home):
        """
        Input:
        <input>/1961/custom1/nodate.jpg

        Output:
        <output/1961/custom1/nodate.jpg  -> image file will have a date of 1961/01/01

        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)
        input_file = create_image_file(self.input_folder.joinpath(YEAR_SPEC).joinpath('custom1'), None)
        output = self.output_folder.joinpath(YEAR_SPEC).joinpath('custom1').joinpath().joinpath(DEFAULT_NAME)

        self.assertTrue(input_file.exists())
        self.assertFalse(output.exists())
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=False)
        await cleaner.run()
        self.assertFalse(input_file.exists())
        self.assertTrue(output.exists())
        new = ImageCleaner(output)
        date = new.date
        self.assertEqual(date, datetime(DATE_SPEC.year, 1, 1))


    @patch('pathlib.Path.home')
    async def test_duplicate_7(self, home):
        """
        Is Registered (existed)
        File contents/names are identical
        paths are the same

            if not entry.is_registered():
            self.print(f'.. File: {entry.path} new file is relocating to {new_path}')
            entry.relocate_file(new_path, register=True, remove=self.remove_file(entry))
        else:
            found = False
            all_entries = deepcopy(entry.get_all_registered())  # save it, in case something new becomes registered
            for value in all_entries:
                if value == entry:  # File contents are identical
                    if value.path == entry.path:
                        found = True
                        if value.path.parent != new_path:
                            self.print(f'.. File: {entry.path} existing file is relocating to {new_path}')
                            entry.relocate_file(new_path, register=True, remove=True)
                        break


        """

    @patch('pathlib.Path.home')
    async def test_rollover_again(self, home):
        """
        ./Input/file.jpg
        ./Output/test_instance_Duplicates/test_instance_NoDate/file.jpg
        ./Output/test_instance_Duplicates/test_instance_NoDate/file_0.jpg

        ./Output/test_instance_NoDate/file.jpg
        ./Output/test_instance_Duplicates/test_instance_NoDate/file_0.jpg
        ./Output/test_instance_Duplicates/test_instance_NoDate/file_2.jpg

        """
        home.return_value = Path(self.temp_base.name)
        input_file = create_image_file(self.input_folder, None, text='foo_new')
        existing1 = create_image_file(self.output_folder.joinpath('test_instance_NoDate'), None,
                                      text='original No Date')
        existing2 = create_image_file(self.output_folder.joinpath('test_instance_NoDate').joinpath('file_0.jpg'), None,
                                      text='original Rolled Over')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             verbose=False, keep_originals=False)
        await cleaner.run()

        self.assertFalse(input_file.exists())
        self.assertTrue(existing1.exists())
        self.assertTrue(existing2.exists())
        self.assertTrue(existing2.parent.joinpath('file_1.jpg').exists())

    @patch('pathlib.Path.home')
    async def test_recursive_folders(self, home):
        """
        ./Input/custom1/custom2/file.jpg

        ./Output/custom1/custom2/file.jpg
        """
        home.return_value = Path(self.temp_base.name)
        create_image_file(self.input_folder.joinpath('custom1').joinpath('custom2'), None)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.keep_original_files = False
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath('custom1').joinpath('custom2').joinpath('file.jpg').exists())

    @patch('pathlib.Path.home')
    async def test_restart_no_changes3(self, home):
        """

            ./Input/1961/9/27/internal_date.jpg
            ./Input/1961/9/27/struct_date.jpg
            ./Input/1961/9/27/19610927-010101.jpg
            ./Input/1961/CustomName/struct_date_custom.jpg
            ./Input/1961/CustomName/19610927-010101_custom.jpg
            ./Input/1961/CustomName/internal_date_custom.jpg
            ./Input/test_instance_NoDate/nodate.jpg
            ./Input/test_instance_NoDate/CustomName/no_date_custom.jpg

        """
        home.return_value = Path(self.temp_base.name)

        file = create_image_file(self.output_folder.joinpath('test_instance_NoDate'), None)
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.input_folder,
                             keep_originals=False, verbose=False)
        await cleaner.run()
        self.assertTrue(file.exists())

    @patch('pathlib.Path.home')
    async def test_restart_no_changes4(self, home):
        """

            ./Input/1961/9/27/internal_date.jpg
            ./Input/1961/9/27/struct_date.jpg
            ./Input/1961/9/27/19610927-010101.jpg
            ./Input/1961/CustomName/struct_date_custom.jpg
            ./Input/1961/CustomName/19610927-010101_custom.jpg
            ./Input/1961/CustomName/internal_date_custom.jpg
            ./Input/test_instance_NoDate/nodate.jpg
            ./Input/test_instance_NoDate/CustomName/no_date_custom.jpg

        """
        home.return_value = Path(self.temp_base.name)

        create_image_file(
            self.input_folder.joinpath(str(DATE_SPEC.year)).joinpath('custom').joinpath('image.jpg'),
            DATE_SPEC)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.input_folder,
                             keep_originals=False, verbose=False)
        await cleaner.run()

        self.assertTrue(self.input_folder.joinpath(str(DATE_SPEC.year)).joinpath('custom').
                        joinpath('image.jpg').exists())

    @patch('pathlib.Path.home')
    async def test_restart_no_changes(self, home):
        """

            ./Input/1961/internal_date.jpg
            ./Input/1961/struct_date.jpg
            ./Input/1961/19610927-010101.jpg
            ./Input/1961/CustomName/struct_date_custom.jpg
            ./Input/1961/CustomName/19610927-010101_custom.jpg
            ./Input/1961/CustomName/internal_date_custom.jpg
            ./Input/test_instance_NoDate/nodate.jpg
            ./Input/test_instance_NoDate/CustomName/no_date_custom.jpg

        """
        home.return_value = Path(self.temp_base.name)

        no_date = create_image_file(self.input_folder.joinpath('test_instance_NoDate'), None)
        internal_date = create_image_file(
            self.input_folder.joinpath(str(DATE_SPEC.year)).joinpath('internal_date.jpg'), DATE_SPEC)
        filename_date = create_image_file(
            self.input_folder.joinpath(str(DATE_SPEC.year)).joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}.jpg'), None)
        struct_date = create_image_file(self.input_folder.joinpath(str(DATE_SPEC.year)).joinpath('struct_date.jpg'), None)
        no_date_custom = create_image_file(self.input_folder.joinpath(self.other_folder).joinpath('no_date_custom.jpg'),
                                           None)
        date_custom = create_image_file(
            self.input_folder.joinpath(str(DATE_SPEC.year)).joinpath('custom').joinpath('internal_date_custom.jpg'),
            None)
        name_custom = create_image_file(self.input_folder.joinpath(str(DATE_SPEC.year)).joinpath('custom').joinpath(
            f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.jpg'), None)
        struct_custom = create_image_file(
            self.input_folder.joinpath(str(DATE_SPEC.year)).joinpath('custom').joinpath('struct_date_custom.jpg'), None)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.input_folder)
        cleaner.keep_original_files = False
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(no_date.exists())
        self.assertTrue(internal_date.exists())
        self.assertTrue(filename_date.exists())
        self.assertTrue(struct_date.exists())
        self.assertTrue(no_date_custom.exists())
        self.assertTrue(date_custom.exists())
        self.assertTrue(name_custom.exists())
        self.assertTrue(struct_custom.exists())

    @patch('pathlib.Path.home')
    async def test_jpg_files(self, home):
        """
            ./Input/nodate.jpg
            ./Input/internal_date.jpg
            ./Input/1961/9/27/struct_date.jpg
            ./Input/19610927-010101.jpg
            ./Input/CustomName/19610927-010101_custom.jpg
            ./Input/CustomName/internal_date_custom.jpg
            ./Input/CustomName/1961/9/27/struct_date_custom.jpg
            ./Input/CustomName/no_date_custom.jpg

            ./Output/1961/9/27/internal_date.jpg
            ./Output/1961/9/27/struct_date.jpg
            ./Output/1961/9/27/19610927-010101.jpg
            ./Output/1961/CustomName/struct_date_custom.jpg
            ./Output/1961/CustomName/19610927-010101_custom.jpg
            ./Output/1961/CustomName/internal_date_custom.jpg
            ./Output/test_instance_NoDate/nodate.jpg
            ./Output/CustomName/no_date_custom.jpg

        """

        home.return_value = Path(self.temp_base.name)

        no_date = create_image_file(self.input_folder, None)
        internal_date = create_image_file(self.input_folder.joinpath('internal_date.jpg'), DATE_SPEC)

        copy_file(no_date, self.input_folder, new_name=f'{DATE_SPEC.strftime("%Y%m%d-010101")}.jpg')
        copy_file(no_date, self.input_folder.joinpath(DIR_SPEC), new_name='struct_date.jpg')
        copy_file(no_date, self.other_folder, new_name='no_date_custom.jpg')
        copy_file(internal_date, self.other_folder, new_name='internal_date_custom.jpg')
        copy_file(no_date, self.other_folder, new_name=f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.jpg')
        copy_file(no_date, self.other_folder.joinpath(DIR_SPEC), new_name='struct_date_custom.jpg')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.verbose = False
        await cleaner.run()

        dirspec = self.output_folder.joinpath(YEAR_SPEC)

        self.assertTrue(self.output_folder.joinpath(cleaner.no_date_base).joinpath(no_date.name).exists())
        self.assertTrue(dirspec.joinpath('internal_date.jpg').exists())
        self.assertTrue(dirspec.joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}.jpg').exists())
        self.assertTrue(dirspec.joinpath('struct_date.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(self.other_folder.name).joinpath('no_date_custom.jpg').exists())
        self.assertTrue(dirspec.joinpath(self.other_folder.name).joinpath('internal_date_custom.jpg').exists())
        self.assertTrue(dirspec.
                        joinpath(self.other_folder.name).joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.jpg')
                        .exists())
        self.assertTrue(dirspec.joinpath(self.other_folder.name).joinpath('struct_date_custom.jpg').exists())

    @patch('pathlib.Path.home')
    async def test_small_files(self, home):
        """
            ./Input/nodate.jpg
            ./Input/internal_date.jpg
            ./Input/1961/9/27/struct_date.jpg
            ./Input/19610927-010101.jpg
            ./Input/CustomName/19610927-010101_custom.jpg
            ./Input/CustomName/internal_date_custom.jpg
            ./Input/CustomName/1961/9/27/struct_date_custom.jpg   (Custom is lost)
            ./Input/CustomName/no_date_custom.jpg

            ./Output/1961/internal_date.jpg
            ./Output/1961/struct_date.jpg
            ./Output/1961/19610927-010101.jpg
            ./Output/1961/CustomName/struct_date_custom.jpg
            ./Output/1961/CustomName/19610927-010101_custom.jpg
            ./Output/1961/CustomName/internal_date_custom.jpg
            ./Output/test_instance_NoDate/nodate.jpg
            ./Output/test_instance_NoDate/CustomName/no_date_custom.jpg

        """

        home.return_value = Path(self.temp_base.name)

        no_date = create_image_file(self.input_folder, None, small=True)
        internal_date = create_image_file(self.input_folder.joinpath('internal_date.jpg'), DATE_SPEC, small=True)

        copy_file(no_date, self.input_folder, new_name=f'{DATE_SPEC.strftime("%Y%m%d-010101")}.jpg')
        copy_file(no_date, self.input_folder.joinpath(DIR_SPEC), new_name='struct_date.jpg')
        copy_file(no_date, self.other_folder, new_name='no_date_custom.jpg')
        copy_file(internal_date, self.other_folder, new_name='internal_date_custom.jpg')
        copy_file(no_date, self.other_folder, new_name=f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.jpg')
        copy_file(no_date, self.other_folder.joinpath(DIR_SPEC), new_name='struct_date_custom.jpg')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.verbose = False
        cleaner.check_for_small = True
        cleaner.check_for_duplicates = True
        await cleaner.run()

        dirspec = self.output_folder.joinpath(cleaner.small_base).joinpath(str(DATE_SPEC.year))
        self.assertTrue(self.output_folder.joinpath(cleaner.small_base).joinpath(cleaner.no_date_base).joinpath(DEFAULT_NAME).exists())
        self.assertTrue(self.output_folder.joinpath(cleaner.small_base).joinpath(cleaner.no_date_base).joinpath(self.other_folder).
                        joinpath('no_date_custom.jpg').exists())

        self.assertTrue(dirspec.joinpath('internal_date.jpg').exists())
        self.assertTrue(dirspec.joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}.jpg').exists())
        self.assertTrue(dirspec.joinpath('struct_date.jpg').exists())

        self.assertTrue(dirspec.joinpath(self.other_folder.name).joinpath('internal_date_custom.jpg').exists())
        self.assertTrue(dirspec.joinpath(self.other_folder.name).joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.jpg').exists())
        self.assertTrue(dirspec. joinpath(self.other_folder.name).joinpath('struct_date_custom.jpg').exists())

    @patch('pathlib.Path.home')
    async def test_mov_files_keep(self, home):

        home.return_value = Path(self.temp_base.name)

        create_image_file(self.input_folder.joinpath('no_date.jpg'), None)
        create_file(self.input_folder.joinpath('no_date.mov'))
        create_file(self.input_folder.joinpath('other_no_date.mov'))

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             keep_originals=True, verbose=False)
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(cleaner.no_date_base).joinpath('no_date.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(cleaner.movies_base).joinpath('no_date.mov').exists())
        self.assertTrue(cleaner.output_folder.joinpath(cleaner.no_date_base).joinpath('other_no_date.mov').exists())
        self.assertEqual(count_files(self.input_folder), 3)
        self.assertEqual(count_files(self.output_folder), 3)

    @patch('pathlib.Path.home')
    async def test_heic_files(self, home):
        """
            ./Input/heic_image.HEIC

            ./Output/2021/10/7/heic_image.jpg
            ./Output/test_instance_Migrated/heic_image.HEIC
            ./Input/heic_image.HEIC
        """
        if platform.system() not in ['Windows', 'win32']:  # pragma: no cover
            home.return_value = Path(self.temp_base.name)
            heic_file = copy_file(self.heic_file, self.input_folder)

            cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
            cleaner.keep_original_files = True
            cleaner.verbose = False
            await cleaner.run()

            self.assertTrue(self.output_folder.joinpath(cleaner.migration_base).joinpath(heic_file.name).exists())
            self.assertTrue(heic_file.exists())
            self.assertTrue(self.output_folder.  # Kludge,  I just know the date on the file.  cheater, cheater
                            joinpath('2021').joinpath(f'{heic_file.stem}.jpg').exists())

    @patch('pathlib.Path.home')
    async def test_heic_no_convert_files(self, home):
        """
            ./Input/heic_image.HEIC

            ./Output/2021/10/7/heic_image.jpg
            ./Output/test_instance_Migrated/heic_image.HEIC
            ./Input/heic_image.HEIC
        """
        if platform.system() not in ['Windows', 'win32']:  # pragma: no cover
            home.return_value = Path(self.temp_base.name)
            heic_file = copy_file(self.heic_file, self.input_folder)

            cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
            cleaner.keep_original_files = True
            cleaner.verbose = False
            cleaner.do_convert = False
            await cleaner.run()

            self.assertFalse(self.output_folder.joinpath(cleaner.migration_base).joinpath(heic_file.name).exists())
            self.assertTrue(heic_file.exists())
            self.assertTrue(self.output_folder.
                            joinpath('test_instance_NoDate').joinpath(heic_file.name).exists())

    @patch('pathlib.Path.home')
    async def test_dup_jpg_new_date(self, home):
        """
            ./Input/1961/9/27/jpeg_image.jpg
            ./Output/test_instance_NoDate/no_date.jpg

            after run
            ./Output/1961/9/27/jpeg_image.jpg
            ./Output/test_instance_Duplicates/test_instance_NoDate/no_date.jpg

        """

        home.return_value = Path(self.temp_base.name)

        create_image_file(self.input_folder.joinpath(DIR_SPEC), None)
        create_image_file(self.output_folder.joinpath('test_instance_NoDate'), None)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             keep_originals=False, verbose=False)
        cleaner.check_for_small = True
        cleaner.check_for_duplicates = True

        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(cleaner.duplicate_base).joinpath(cleaner.no_date_base).joinpath(DEFAULT_NAME).exists())
        self.assertTrue(self.output_folder.joinpath(str(DATE_SPEC.year)).joinpath(DEFAULT_NAME).exists())
        self.assertEqual(count_files(self.output_folder), 2)

    @patch('pathlib.Path.home')
    async def test_dup_jpg_no_date_again(self, home):
        """

            Files are all the same,

            ./Output/test_instance_Duplicates/test_instance_NoDate/file.jpg
            ./Output/1961/9/27/file.jpg
            ./Input/file.jpg

            after run
            ./Output/1961/9/27/file.jpg
            ./Output/test_instance_Duplicates/test_instance_NoDate/file.jpg

        """

        home.return_value = Path(self.temp_base.name)

        create_image_file(self.output_folder.joinpath(DIR_SPEC), None)
        create_image_file(self.input_folder, None)
        create_image_file(self.output_folder.joinpath('test_instance_Duplicates').joinpath('test_instance_NoDate'),
                          None)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             keep_originals=False, verbose=False)
        cleaner.check_for_small = True
        cleaner.check_for_duplicates = True

        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath('file.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(cleaner.duplicate_base).joinpath(cleaner.no_date_base).joinpath('file.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(cleaner.duplicate_base).joinpath(cleaner.no_date_base).joinpath('file_0.jpg').exists())

        self.assertEqual(count_files(self.output_folder), 3)

    @patch('pathlib.Path.home')
    async def test_dup_jpg_old_date(self, home):
        """
            ./Input/1961/9/27/file.jpg
            ./Output/test_instance_NoDate/file.jpg

            after run
            ./Output/1961/9/27/file.jpg
            ./Output/test_instance_Duplicates/test_instance_NoDate/file.jpg

        """

        home.return_value = Path(self.temp_base.name)

        create_image_file(self.output_folder.joinpath(DIR_SPEC), None)
        create_image_file(self.input_folder, None)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             keep_originals=False, verbose=False)
        cleaner.check_for_small = True
        cleaner.check_for_duplicates = True

        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(cleaner.duplicate_base).joinpath(cleaner.no_date_base).joinpath('file.jpg').exists())
        self.assertTrue(self.output_folder.joinpath().joinpath('file.jpg').exists())

        self.assertEqual(count_files(self.output_folder), 2)

    @patch('pathlib.Path.home')
    async def test_duplicate_jpg_files_with_duplicates(self, home):
        """
            ./Input/jpeg_image.jpg  <- Internal Date
            ./Input/1961/9/27/jpeg_image.jpg
            ./Input/no_date.jpg
            ./Input/CustomName/jpeg_image.jpg  <- Internal Date
            ./Input/CustomName/1961/9/27/jpeg_image.jpg
            ./Input/CustomName/no_date.jpg

            Imported
            ./Output/1961/9/27/jpeg_image.jpg - ack (internal)
            ./Output/1961/CustomName/jpeg_image.jpg - ack (internal)
            ./Output/test_instance_Duplicates/1961/9/27/jpeg_image.jpg - ack (structure)
            ./Output/test_instance_Duplicates/1961/CustomName/jpeg_image.jpg - ack (structure)
            ./Output/test_instance_NoDate/no_date.jpg - ack (no date)
            ./Output/CustomName/no_date.jpg - ack (custom no date)

            Post Processed
            ./Output/1961/CustomName/jpeg_image.jpg
            ./Output/test_instance_Duplicates/1961/9/27/jpeg_image.jpg
            ./Output/test_instance_Duplicates/1961/9/27/jpeg_image_0.jpg
            ./Output/test_instance_Duplicates/1961/CustomName/jpeg_image.jpg
            ./Output/test_instance_Duplicates/test_instance_NoDate/no_date.jpg
            ./Output/CustomName/no_date.jpg



        """

        home.return_value = Path(self.temp_base.name)

        no_date = create_image_file(self.input_folder.joinpath('no_date.jpg'), None, text='Same File')
        internal_date = create_image_file(self.input_folder.joinpath('jpeg_image.jpg'), DATE_SPEC, text='Same File')

        copy_file(no_date, self.other_folder)
        copy_file(no_date, self.input_folder.joinpath(DIR_SPEC), new_name=internal_date.name)
        copy_file(internal_date, self.other_folder, new_name=internal_date.name)
        copy_file(no_date, self.input_folder.joinpath('custom').joinpath(DIR_SPEC), new_name=internal_date.name)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             keep_originals=False, verbose=False)
        cleaner.check_for_small = True
        cleaner.check_for_duplicates = True

        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(str(DATE_SPEC.year)).joinpath(self.other_folder.name).
                        joinpath(internal_date.name).exists())

        self.assertTrue(self.output_folder.joinpath(cleaner.duplicate_base).joinpath(str(DATE_SPEC.year)).joinpath('custom').
                        joinpath(internal_date.name).exists())
        self.assertTrue(self.output_folder.joinpath(cleaner.duplicate_base).joinpath(str(DATE_SPEC.year)).joinpath('jpeg_image.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(cleaner.duplicate_base).joinpath(str(DATE_SPEC.year)).joinpath('jpeg_image_0.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(cleaner.duplicate_base).joinpath(cleaner.no_date_base).joinpath('no_date.jpg').exists())

        self.assertTrue(self.output_folder.joinpath(self.other_folder.name).joinpath('no_date.jpg').exists())

        self.assertEqual(count_files(self.output_folder), 6)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    async def test_dup_jpg_files_earlier_date(self, home):
        """
            Date storage is based on the earliest of folder dates is no dates on images

            ./Input/jpeg_image
            ./Input/1961/9/27/jpeg_image.jpg
            ./Input/1961/9/28/jpeg_image.jpg

            ./Output/1961/jpeg_image.jpg
            ./Output/test_instance_Duplicates/1961/jpeg_image.jpg
            ./Output/test_instance_Duplicates/test_instance_NoDate/jpeg_image.jpg
        """

        home.return_value = Path(self.temp_base.name)

        next_day = Path(str(DATE_SPEC.year)).joinpath(str(DATE_SPEC.month + 1)).joinpath(str(DATE_SPEC.day))

        create_image_file(self.input_folder, None)
        create_image_file(self.input_folder.joinpath(DIR_SPEC), None)
        create_image_file(self.input_folder.joinpath(next_day), None)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             keep_originals=False, verbose=True)
        cleaner.check_for_small = True
        cleaner.check_for_duplicates = True

        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(YEAR_SPEC).joinpath('file.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(cleaner.duplicate_base).joinpath(YEAR_SPEC).joinpath('file.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(cleaner.duplicate_base).joinpath(cleaner.no_date_base).joinpath('file.jpg').exists())
        self.assertEqual(count_files(self.output_folder), 3)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    async def test_dup_jpg_files_custom_no_dates(self, home):
        """
            ./Input/custom1/jpeg_image.jpg
            ./Input/custom3/jpeg_image.jpg

            # existing
            ./Output/custom2/jpeg_image.jpg

            Result:
            ./Output/custom1/jpeg_image.jpg
            ./Output/custom2/jpeg_image.jpg
            ./Output/custom3/jpeg_image.jpg
        """

        home.return_value = Path(self.temp_base.name)

        create_image_file(self.input_folder.joinpath('custom1'), None)
        create_image_file(self.input_folder.joinpath('custom2'), None)
        create_image_file(self.input_folder.joinpath('custom3'), None)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             keep_originals=False, verbose=False)
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath('custom1').joinpath(DEFAULT_NAME).exists())
        self.assertTrue(self.output_folder.joinpath('custom2').joinpath(DEFAULT_NAME).exists())
        self.assertTrue(self.output_folder.joinpath('custom3').joinpath(DEFAULT_NAME).exists())

        self.assertEqual(count_files(self.output_folder), 3)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    async def test_dup_jpg_files_custom_with_date(self, home):
        """

            ./Input/custom1/jpeg_image.jpg
            ./Input/custom3/jpeg_image.jpg - with a date

            # existing
            ./Output/custom2/jpeg_image.jpg

            Result:
            ./Output/duplicates/custom1/jpeg_image.jpg
            ./Output/custom2/jpeg_image.jpg
            ./Output/YYYY/custom3/jpeg_image.jpg
        """

        home.return_value = Path(self.temp_base.name)

        create_image_file(self.input_folder.joinpath('custom1').joinpath('file.jpg'), date=None)
        create_image_file(self.input_folder.joinpath('custom2').joinpath('file.jpg'), date=None)
        create_image_file(self.input_folder.joinpath('custom3').joinpath('file.jpg'), date=DATE_SPEC)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             keep_originals=False, verbose=False)
        await cleaner.run()

        self.assertTrue(self.output_folder.
                        joinpath(str(DATE_SPEC.year)).joinpath('custom3').joinpath('file.jpg').exists())
        self.assertTrue(self.output_folder.joinpath('custom2').joinpath('file.jpg').exists())
        self.assertTrue(self.output_folder.joinpath('custom1').joinpath('file.jpg').exists())

        self.assertEqual(count_files(self.output_folder), 3)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    async def test_dup_jpg_files_custom_with_date_dont_care(self, home):
        """

            ./Input/custom1/jpeg_image.jpg - with date

            # existing

            Result:
            ./Output/YYYY/MM/DD/jpeg_image.jpg
        """

        home.return_value = Path(self.temp_base.name)

        create_image_file(self.input_folder.joinpath('custom3').joinpath('file.jpg'), date=DATE_SPEC)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             keep_originals=False, verbose=False, check_description=False)
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(YEAR_SPEC).joinpath('file.jpg').exists())
        self.assertEqual(count_files(self.output_folder), 1)
        self.assertEqual(count_files(self.input_folder), 0)


    @patch('pathlib.Path.home')
    async def test_dup_jpg_files_custom_date2(self, home):
        """
            ./Input/1961/9/27/jpeg_image.jpg  (no internal date)
            # existing
            ./Output/1961/jpeg_image.jpg  (internal date of 1961/9/28

            Result:
            ./Output/test_instance_Duplicates/1961/jpeg_image.jpg (internal date)
            ./Output/1961/jpeg_image.jpg (no internal date)
        """

        home.return_value = Path(self.temp_base.name)

        input_file = create_image_file(self.input_folder.joinpath(DIR_SPEC), None)
        output_file = create_image_file(self.output_folder.joinpath('1961'), DATE_SPEC + timedelta(days=1))

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             keep_originals=False, verbose=False)
        cleaner.check_for_small = True
        cleaner.check_for_duplicates = True

        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(YEAR_SPEC).joinpath(input_file.name).exists())
        self.assertTrue(self.output_folder.joinpath(cleaner.duplicate_base).joinpath(YEAR_SPEC).joinpath(output_file.name).exists())
        self.assertEqual(count_files(self.output_folder), 2)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    async def test_dup_jpg_files_internal_date1(self, home):
        """
            ./Input/1961/9/27/jpeg_image.jpg
            # existing
            ./Output/1961/9/28/jpeg_image.jpg

            Result:
            ./Output/test_instance_Duplicates/1961/9/28/jpeg_image.jpg
            ./Output/1961/9/27/jpeg_image.jpg
        """

        home.return_value = Path(self.temp_base.name)

        next_day = Path(str(DATE_SPEC.year)).joinpath(str(DATE_SPEC.month)).joinpath(str(DATE_SPEC.day + 1))
        create_image_file(self.input_folder.joinpath(DIR_SPEC), DATE_SPEC)
        create_image_file(self.output_folder.joinpath(next_day), DATE_SPEC + timedelta(days=1))

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             keep_originals=False, verbose=False)
        cleaner.check_for_small = True
        cleaner.check_for_duplicates = True

        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(str(DATE_SPEC.year)).joinpath(DEFAULT_NAME).exists())
        self.assertTrue(self.output_folder.joinpath(cleaner.duplicate_base).joinpath(next_day).joinpath(DEFAULT_NAME).exists())
        self.assertEqual(count_files(self.output_folder), 2)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    async def test_dup_jpg_files_internal_date2(self, home):
        """
            ./Input/1961/9/27/jpeg_image.jpg
            # existing
            ./Output/1961/9/28/jpeg_image.jpg

            Result:
            ./Output/test_instance_Duplicates/1961/9/28/jpeg_image.jpg
            ./Output/1961/9/27/jpeg_image.jpg
        """

        home.return_value = Path(self.temp_base.name)

        next_day = Path(str(DATE_SPEC.year)).joinpath(str(DATE_SPEC.month)).joinpath(str(DATE_SPEC.day + 1))
        create_image_file(self.output_folder.joinpath(DIR_SPEC), DATE_SPEC)
        create_image_file(self.input_folder.joinpath(next_day), DATE_SPEC + timedelta(days=1))
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             keep_originals=False, verbose=False)
        cleaner.check_for_small = True
        cleaner.check_for_duplicates = True

        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(str(DATE_SPEC.year)).joinpath(DEFAULT_NAME).exists())
        self.assertTrue(self.output_folder.joinpath(cleaner.duplicate_base).joinpath(next_day).joinpath(DEFAULT_NAME).exists())
        self.assertEqual(count_files(self.output_folder), 2)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    async def test_dup_jpg_files_internal_date3(self, home):
        """
            ./Input/1961/9/27/jpeg_image.jpg
            # existing
            ./Output/1961/9/28/jpeg_image.jpg

            Result:
            ./Output/test_instance_Duplicates/1961/9/28/jpeg_image.jpg
            ./Output/1961/9/27/jpeg_image.jpg
        """

        home.return_value = Path(self.temp_base.name)

        next_day = Path(str(DATE_SPEC.year)).joinpath(str(DATE_SPEC.month)).joinpath(str(DATE_SPEC.day + 1))

        create_image_file(self.output_folder.joinpath(DIR_SPEC), DATE_SPEC)
        create_image_file(self.input_folder.joinpath(next_day), DATE_SPEC)
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             keep_originals=False, verbose=False)
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath(DEFAULT_NAME).exists())
        self.assertTrue(self.output_folder.joinpath(cleaner.duplicate_base).joinpath(str(DATE_SPEC.year)).joinpath(DEFAULT_NAME).exists())
        self.assertEqual(count_files(self.output_folder), 2)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    async def test_dup_jpg_files_internal_date4(self, home):
        """
            ./Input/1961/9/27/jpeg_image.jpg
            # existing
            ./Output/1961/9/28/jpeg_image.jpg

            Result:
            ./Output/test_instance_Duplicates/1961/9/28/jpeg_image.jpg
            ./Output/1961/9/27/jpeg_image.jpg
        """

        home.return_value = Path(self.temp_base.name)

        next_day = Path(str(DATE_SPEC.year)).joinpath(str(DATE_SPEC.month)).joinpath(str(DATE_SPEC.day + 1))
        create_image_file(self.input_folder.joinpath(DIR_SPEC), DATE_SPEC)
        create_image_file(self.output_folder.joinpath(next_day), DATE_SPEC)  # Stored on the wrong date.

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             keep_originals=False, verbose=False)
        cleaner.check_for_small = True
        cleaner.check_for_duplicates = True

        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(str(DATE_SPEC.year)).joinpath('file.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(cleaner.duplicate_base).joinpath(next_day).joinpath('file.jpg').exists())
        self.assertEqual(count_files(self.output_folder), 2)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    async def test_dup_jpg_files_custom_over_date(self, home):
        """
            ./Input/1961/9/27/jpeg_image.jpg
            # existing
            ./Output/1961/9/28/jpeg_image.jpg

            Result:
            ./Output/test_instance_Duplicates/1961/9/28/jpeg_image.jpg
            ./Output/1961/9/27/jpeg_image.jpg
        """

        home.return_value = Path(self.temp_base.name)

        create_image_file(self.output_folder.joinpath('custom'), None)
        create_image_file(self.input_folder.joinpath(DIR_SPEC), None)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             keep_originals=False, verbose=False)
        cleaner.check_for_small = True
        cleaner.check_for_duplicates = True

        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath('custom').joinpath(DEFAULT_NAME))
        self.assertTrue(self.output_folder.joinpath(cleaner.duplicate_base).joinpath(YEAR_SPEC).joinpath(DEFAULT_NAME).exists())
        self.assertEqual(count_files(self.output_folder), 2)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    async def test_txt_files(self, home):
        """
            ./Input/nodate.txt
            ./Input/internal_date.txt
            ./Input/1961/9/27/struct_date.txt
            ./Input/19610927-010101.txt
            ./Input/CustomName/19610927-010101_custom.txt
            ./Input/CustomName/internal_date_custom.txt
            ./Input/CustomName/1961/9/27/struct_date_custom.txt   (Custom is lost)
            ./Input/CustomName/no_date_custom.txt

            Nothing is processed

        """

        home.return_value = Path(self.temp_base.name)
        no_date = create_file(self.input_folder.joinpath('nodata.txt'))
        internal_date = create_image_file(self.input_folder, DATE_SPEC,)
        copy_file(internal_date, self.input_folder, 'internal_date.txt')

        copy_file(no_date, self.input_folder, new_name=f'{DATE_SPEC.strftime("%Y%m%d-010101")}.txt')
        copy_file(no_date, self.input_folder.joinpath(DIR_SPEC), new_name='struct_date.txt')
        copy_file(no_date, self.input_folder.joinpath('custom'), new_name='no_date_custom.txt')
        copy_file(internal_date, self.input_folder.joinpath('custom'), new_name='internal_date_custom.txt')
        copy_file(no_date, self.input_folder.joinpath('custom'), new_name=f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.txt')
        copy_file(no_date, self.input_folder.joinpath('custom').joinpath(DIR_SPEC), new_name='struct_date_custom.txt')

        internal_date.unlink()

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             keep_originals=False, verbose=False)
        await cleaner.run()

        self.assertFalse(cleaner.output_folder.joinpath(cleaner.no_date_base).joinpath('nodate.txt').exists())
        self.assertFalse(self.output_folder.joinpath(DIR_SPEC).joinpath('internal_date.txt').exists())
        self.assertFalse(self.output_folder.joinpath(DIR_SPEC).
                         joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}.txt').exists())
        self.assertFalse(self.output_folder.joinpath(DIR_SPEC).
                         joinpath('struct_date.txt').exists())
        self.assertFalse(cleaner.output_folder.joinpath(cleaner.no_date_base).
                         joinpath('custom').joinpath('no_date_custom.txt').exists())
        self.assertFalse(self.output_folder.joinpath(str(DATE_SPEC.year)).
                         joinpath('custom').joinpath('internal_date_custom.txt').exists())
        self.assertFalse(self.output_folder.joinpath(str(DATE_SPEC.year)).
                         joinpath('custom').joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.txt')
                         .exists())
        self.assertFalse(self.output_folder.joinpath(str(DATE_SPEC.year)).
                         joinpath('custom').joinpath('struct_date_custom.txt').exists())
        self.assertEqual(count_files(self.output_folder.joinpath('custom')), 0)
        self.assertEqual(count_files(self.input_folder), 8)


class InitTest(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        super().setUp()
        self.tempdir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        # print(f'\n{str(self)} - {self.tempdir.name}')

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
        self.assertTrue(app.do_convert, "Conversion are not True")
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
            self.assertTrue(app.do_convert, "Conversion are not True")
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
        if platform.system() not in ['Windows', 'win32']: # pragma: no cover
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
            self.assertTrue(app.in_place, 'In place is not set')

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
        print(f'Testing {self._testMethodName}')
        self.my_location = Path(os.path.dirname(__file__))
        self.app_name = 'test_instance'

        # Make basic folders
        self.temp_base = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.output_folder = Path(self.temp_base.name).joinpath('Output')
        self.input_folder = Path(self.temp_base.name).joinpath('Input')

        os.mkdir(self.output_folder)
        os.mkdir(self.input_folder)

        # self.heic_file = self.my_location.joinpath('data').joinpath('heic_image.HEIC')

    @patch('pathlib.Path.home')
    async def test_same_file(self, home):
        """
        starting - output/custom/file.jpg   running with input == output
        ending - output/<no_date_base>/custom/file.jpg
        :param home:
        :return:
        """
        home.return_value = Path(self.temp_base.name)
        orig = create_image_file(self.output_folder.joinpath('custom'), None)
        cleaner = ImageClean(self.app_name, input=self.output_folder, output=self.output_folder, verbose=False)
        new = self.output_folder.joinpath(cleaner.no_date_base).joinpath('custom').joinpath(orig.name)
        await cleaner.run()
        self.assertTrue(new.exists())
        self.assertFalse(orig.exists())

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

    @patch('pathlib.Path.home')
    async def test_output_created(self, home):
        home.return_value = Path(self.temp_base.name)
        new_out = Path(self.temp_base.name).joinpath('output2')
        self.assertFalse(new_out.exists())
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=new_out)
        await cleaner.run()
        self.assertTrue(new_out.exists())

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
    @patch('pathlib.Path.home')
    async def test_audit_folders(self, home):
        home.return_value = Path(self.temp_base.name)

        one = create_image_file(self.input_folder.joinpath('one.jpg'), DATE_SPEC, text='Same File')
        two = create_image_file(self.output_folder.joinpath(DIR_SPEC).joinpath('two.jpg'), DATE_SPEC, text='Same File')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder,
                             keep_originals=True, verbose=False)
        await cleaner.run()
        self.assertTrue(self.output_folder.joinpath(str(DATE_SPEC.year)).joinpath(one.name).exists())
        self.assertTrue(self.output_folder.joinpath(str(DATE_SPEC.year)).joinpath(two.name).exists())
        self.assertTrue(one.exists())

    @patch('backend.image_clean.WARNING_FOLDER_SIZE', 2)
    @patch('builtins.print')
    @patch('pathlib.Path.home')
    async def test_audit_folders_2(self, home, my_print):
        home.return_value = Path(self.temp_base.name)
        create_image_file(self.output_folder.joinpath(DIR_SPEC).joinpath('one.jpg'), DATE_SPEC)
        create_image_file(self.output_folder.joinpath(DIR_SPEC).joinpath('two.jpg'), DATE_SPEC)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder, verbose=True)
        await cleaner.run()
        found = False
        for call_item in my_print.call_args_list:
            if call_item.args[0].strip().startswith('VERY large folder'):
                found = True  # pragma: no cover
        self.assertFalse(found, 'Very large folder found')

        CleanerBase.clear_caches()
        create_image_file(self.output_folder.joinpath(DIR_SPEC).joinpath('three.jpg'), DATE_SPEC)
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder, verbose=True)
        await cleaner.run()
        found = False
        print(f'Size of my_print:{len(my_print.call_args_list)}')
        for call_item in my_print.call_args_list:  # pragma: no cover
            print('Called this unreached code')
            if call_item.args[0].strip().startswith('VERY large folder'):
                found = True
                break
        self.assertTrue(found, 'Very large folder not found')

    @patch('pathlib.Path.home')
    def test_compare_folders(self, home):
        # pylint: disable=protected-access arguments-out-of-order
        home.return_value = Path(self.temp_base.name)
        root = FolderCleaner(Path('/a/b/c'), None)
        cleaner = ImageClean(self.app_name)
        folder1 = FolderCleaner(Path('/a/b/c/folder1'), root)
        folder2 = FolderCleaner(Path('/a/b/c/folder2'), root)
        self.assertEqual(cleaner._folder_test(folder1, folder2), 0, 'Identical')
        folder2 = FolderCleaner(Path(f'a/b/c/{self.app_name}_folder2'), root)
        self.assertEqual(cleaner._folder_test(folder1, folder2), 1, 'Custom is greater')
        self.assertEqual(cleaner._folder_test(folder2, folder1), 2, 'Generic is less')
        folder1 = FolderCleaner(Path(f'a/b/c/{self.app_name}_folder1'), root)
        self.assertEqual(cleaner._folder_test(folder1, folder2), 0, 'Identical')

        folder1._date = DATE_SPEC
        self.assertEqual(cleaner._folder_test(folder1, folder2), 1, 'Younger is greater')
        self.assertEqual(cleaner._folder_test(folder2, folder1), 2, 'Older is less')

        folder2._date = DATE_SPEC + timedelta(days=1)
        self.assertEqual(cleaner._folder_test(folder1, folder2), 1, 'Younger is greater')
        self.assertEqual(cleaner._folder_test(folder2, folder1), 2, 'Older is less')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
