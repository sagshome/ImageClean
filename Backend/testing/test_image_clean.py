"""
Test Cases for the Image Clean classes
"""
# pylint: disable=too-many-lines
# pylint: disable=line-too-long
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring

import asyncio
import os
import stat
import sys
import tempfile
import unittest

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from Backend.cleaner import Cleaner
from Backend.image_clean import ImageClean
from Utilities.test_utilities import create_image_file, count_files, set_date, copy_file, DATE_SPEC, DIR_SPEC

sys.path.append(f'{Path.home().joinpath("ImageClean")}')  # I got to figure out this hack,
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))


class ActualScenarioTest(unittest.IsolatedAsyncioTestCase):
    """
    Create real world scenerio's for testing.   This is perhaps not unit tests but system tests

    These tests cover all the duplicate scenerios


    """
    # pylint: disable=too-many-public-methods, too-many-instance-attributes
    def tearDown(self):
        self.temp_base.cleanup()
        Cleaner.clear_caches()
        super(ActualScenarioTest, self).tearDown()

    def setUp(self):
        super(ActualScenarioTest, self).setUp()
        self.my_location = Path(os.path.dirname(__file__))
        self.app_name = 'test_instance'
        self.other_folder_name = 'CustomName'

        # Make basic folders
        self.temp_base = tempfile.TemporaryDirectory()
        self.output_folder = Path(self.temp_base.name).joinpath('Output')
        self.input_folder = Path(self.temp_base.name).joinpath('Input')
        self.other_folder = self.input_folder.joinpath(self.other_folder_name)

        os.mkdir(self.output_folder)
        os.mkdir(self.input_folder)
        os.mkdir(self.other_folder)

        self.small_file = self.my_location.joinpath('data').joinpath('small_image.jpg')
        self.heic_file = self.my_location.joinpath('data').joinpath('heic_image.HEIC')
        self.jpg_file = self.my_location.joinpath('data').joinpath('jpeg_image.jpg')

        # print(f'{str(self)} - {self.temp_base.name}')

    @patch('pathlib.Path.home')
    async def test_rollover_again(self, home):
        """
        ./Input/file.jpg
        ./Output/test_instance_NoDate/file.jpg
        ./Output/test_instance_Duplicates/test_instance_NoDate/file.jpg
        ./Output/test_instance_Duplicates/test_instance_NoDate/file_0.jpg

        ./Output/test_instance_NoDate/file.jpg
        ./Output/test_instance_Duplicates/test_instance_NoDate/file_0.jpg
        ./Output/test_instance_Duplicates/test_instance_NoDate/file_2.jpg

        """
        home.return_value = Path(self.temp_base.name)
        input_file = create_image_file(self.input_folder, None, text='foo_new')
        existing1 = create_image_file(self.output_folder.joinpath('test_instance_NoDate'), None, text='original No Date')
        existing2 = create_image_file(self.output_folder.joinpath('test_instance_NoDate').joinpath('file_0.jpg'), None, text='original Rolled Over')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.verbose = False
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
        cleaner.set_keep_original_files(False)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath('custom1').joinpath('custom2').joinpath('file.jpg').exists())

    @patch('pathlib.Path.home')
    async def test_restart_ignore_custom_folder(self, home):
        """

            ./Input/1961/9/27/internal_date.jpg
            ./Input/1961/9/27/struct_date.jpg
            ./Input/1961/9/27/19610927-010101.jpg
            ./Input/1961/CustomName/struct_date_custom.jpg
            ./Input/1961/CustomName/19610927-010101_custom.jpg
            ./Input/1961/CustomName/internal_date_custom.jpg
            ./Input/test_instance_NoDate/nodate.jpg
            ./Input/test_instance_NoDate/CustomName/no_date_custom.jpg

            after

            ./Input/1961/9/27/internal_date.jpg
            ./Input/1961/9/27/struct_date.jpg
            ./Input/1961/9/27/19610927-010101.jpg
            ./Input/1961/1/1/struct_date_custom.jpg  <- date flops top 1/1 since we have no date data other then 1961
            ./Input/1961/9/27/19610927-010101_custom.jpg
            ./Input/1961/9/27/internal_date_custom.jpg
            ./Input/test_instance_NoDate/nodate.jpg
            ./Input/test_instance_NoDate/no_date_custom.jpg

        """
        home.return_value = Path(self.temp_base.name)

        create_image_file(self.input_folder.joinpath('test_instance_NoDate'), None)
        create_image_file(self.input_folder.joinpath(DIR_SPEC).joinpath('internal_date.jpg'), DATE_SPEC)
        create_image_file(
            self.input_folder.joinpath(DIR_SPEC).joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}.jpg'), None)
        create_image_file(self.input_folder.joinpath(DIR_SPEC).joinpath('struct_date.jpg'), None)
        create_image_file(self.input_folder.joinpath('custom').joinpath('no_date_custom.jpg'), None)
        create_image_file(
            self.input_folder.joinpath(str(DATE_SPEC.year)).joinpath('custom').joinpath('internal_date_custom.jpg'),
            DATE_SPEC)
        create_image_file(self.input_folder.joinpath(str(DATE_SPEC.year)).joinpath('custom').joinpath(
            f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.jpg'), None)
        create_image_file(
            self.input_folder.joinpath(str(DATE_SPEC.year)).joinpath('custom').joinpath('struct_date_custom.jpg'), None)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.input_folder)
        cleaner.set_keep_original_files(False)
        cleaner.verbose = True
        cleaner.add_bad_parents('custom')
        await cleaner.run()

        self.assertTrue(self.input_folder.joinpath('test_instance_NoDate').exists(), 'test_instance_NoDate')
        self.assertTrue(self.input_folder.joinpath(DIR_SPEC).joinpath('internal_date.jpg').exists(), 'internal_date.jpg')
        self.assertTrue(
            self.input_folder.joinpath(DIR_SPEC).joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}.jpg').exists(), f'{DATE_SPEC.strftime("%Y%m%d-010101")}.jpg')
        self.assertTrue(self.input_folder.joinpath(DIR_SPEC).joinpath('struct_date.jpg').exists(), 'struct_date.jpg')
        self.assertTrue(self.input_folder.joinpath('test_instance_NoDate').joinpath('no_date_custom.jpg').exists(), 'no_date_custom.jpg')
        self.assertTrue(self.input_folder.joinpath(DIR_SPEC).joinpath('internal_date_custom.jpg').exists(), 'internal_date_custom.jpg')
        self.assertTrue(
            self.input_folder.joinpath(DIR_SPEC).joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.jpg').exists(), f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.jpg')
        self.assertTrue(
            self.input_folder.joinpath(str(DATE_SPEC.year)).joinpath('1').joinpath('1').joinpath(
                'struct_date_custom.jpg').exists(), 'struct_date_custom.jpg')

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

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.input_folder)
        cleaner.set_keep_original_files(False)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(self.input_folder.joinpath(str(DATE_SPEC.year)).joinpath('custom').joinpath('image.jpg').exists())

    @patch('pathlib.Path.home')
    async def test_restart_no_changes(self, home):
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

        no_date = create_image_file(self.input_folder.joinpath('test_instance_NoDate'), None)
        internal_date = create_image_file(self.input_folder.joinpath(DIR_SPEC).joinpath('internal_date.jpg'), DATE_SPEC)
        filename_date = create_image_file(
            self.input_folder.joinpath(DIR_SPEC).joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}.jpg'), None)
        struct_date = create_image_file(self.input_folder.joinpath(DIR_SPEC).joinpath('struct_date.jpg'), None)
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
        cleaner.set_keep_original_files(False)
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
    async def test_jpg_files_single(self, home):
        """

            ./Output/CustomName/no_date_custom.jpg

            invalidate CustomName

            ./Output/test_instance_NoDate/no_date_custom.jpg

        """

        home.return_value = Path(self.temp_base.name)

        create_image_file(self.input_folder.joinpath('custom'), None)
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.verbose = False
        cleaner.add_bad_parents('custom')
        await cleaner.run()

        self.assertTrue(cleaner.no_date_path.joinpath('file.jpg').exists())

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

        self.assertTrue(cleaner.no_date_path.joinpath(no_date.name).exists())
        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath('internal_date.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).
                        joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).
                        joinpath('struct_date.jpg').exists())
        self.assertTrue(self.output_folder.
                        joinpath(self.other_folder.name).joinpath('no_date_custom.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(str(DATE_SPEC.year)).
                        joinpath(self.other_folder.name).joinpath('internal_date_custom.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(str(DATE_SPEC.year)).
                        joinpath(self.other_folder.name).joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.jpg')
                        .exists())
        self.assertTrue(self.output_folder.joinpath(str(DATE_SPEC.year)).
                        joinpath(self.other_folder.name).joinpath('struct_date_custom.jpg').exists())

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

            ./Output/1961/9/27/internal_date.jpg
            ./Output/1961/9/27/struct_date.jpg
            ./Output/1961/9/27/19610927-010101.jpg
            ./Output/1961/CustomName/struct_date_custom.jpg
            ./Output/1961/CustomName/19610927-010101_custom.jpg
            ./Output/1961/CustomName/internal_date_custom.jpg
            ./Output/test_instance_NoDate/nodate.jpg
            ./Output/test_instance_NoDate/CustomName/no_date_custom.jpg

        """

        home.return_value = Path(self.temp_base.name)
        no_date = copy_file(self.small_file, self.input_folder, new_name='nodate.jpg')
        set_date(no_date, None)

        internal_date = copy_file(self.small_file, self.input_folder, new_name='internal_date.jpg')
        set_date(internal_date, DATE_SPEC)

        copy_file(no_date, self.input_folder, new_name=f'{DATE_SPEC.strftime("%Y%m%d-010101")}.jpg')
        copy_file(no_date, self.input_folder.joinpath(DIR_SPEC), new_name='struct_date.jpg')
        copy_file(no_date, self.other_folder, new_name='no_date_custom.jpg')
        copy_file(internal_date, self.other_folder, new_name='internal_date_custom.jpg')
        copy_file(no_date, self.other_folder, new_name=f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.jpg')
        copy_file(no_date, self.other_folder.joinpath(DIR_SPEC), new_name='struct_date_custom.jpg')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(cleaner.small_path.joinpath(cleaner.no_date_base).joinpath('nodate.jpg').exists())
        self.assertTrue(cleaner.small_path.joinpath(DIR_SPEC).joinpath('internal_date.jpg').exists())
        self.assertTrue(cleaner.small_path.joinpath(DIR_SPEC).
                        joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}.jpg').exists())
        self.assertTrue(cleaner.small_path.joinpath(DIR_SPEC).
                        joinpath('struct_date.jpg').exists())
        self.assertTrue(cleaner.small_path.
                        joinpath(self.other_folder.name).joinpath('no_date_custom.jpg').exists())
        self.assertTrue(cleaner.small_path.joinpath(str(DATE_SPEC.year)).
                        joinpath(self.other_folder.name).joinpath('internal_date_custom.jpg').exists())
        self.assertTrue(cleaner.small_path.joinpath(str(DATE_SPEC.year)).
                        joinpath(self.other_folder.name).joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.jpg')
                        .exists())
        self.assertTrue(cleaner.small_path.joinpath(str(DATE_SPEC.year)).
                        joinpath(self.other_folder.name).joinpath('struct_date_custom.jpg').exists())

    @patch('pathlib.Path.home')
    async def test_mov_files_keep(self, home):

        home.return_value = Path(self.temp_base.name)
        no_date_mov = copy_file(self.jpg_file, self.input_folder, new_name='no_date.mov')
        set_date(no_date_mov, None)
        copy_file(no_date_mov, self.input_folder, new_name='no_date.jpg')
        copy_file(no_date_mov, self.input_folder, new_name='other_no_date.mov')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_movie_clips(True)
        cleaner.set_keep_original_files(True)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(cleaner.no_date_path.joinpath('no_date.jpg').exists())
        self.assertTrue(cleaner.image_movies_path.joinpath('no_date.mov').exists())
        self.assertTrue(cleaner.no_date_path.joinpath('other_no_date.mov').exists())
        self.assertEqual(count_files(self.input_folder), 3)
        self.assertEqual(count_files(self.output_folder), 3)

    @patch('pathlib.Path.home')
    async def test_mov_files_no_keep(self, home):

        home.return_value = Path(self.temp_base.name)
        no_date_mov = copy_file(self.jpg_file, self.input_folder, new_name='no_date.mov')
        set_date(no_date_mov, None)
        copy_file(no_date_mov, self.input_folder, new_name='no_date.jpg')
        copy_file(no_date_mov, self.input_folder, new_name='other_no_date.mov')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_movie_clips(False)
        cleaner.set_keep_original_files(False)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(cleaner.no_date_path.joinpath('no_date.jpg').exists())
        self.assertTrue(cleaner.no_date_path.joinpath('other_no_date.mov').exists())
        self.assertEqual(count_files(self.input_folder), 0)
        self.assertEqual(count_files(self.output_folder), 2)

    @patch('pathlib.Path.home')
    async def test_heic_files(self, home):
        """
            ./Input/heic_image.HEIC

            ./Output/2021/10/7/heic_image.jpg
            ./Output/test_instance_Migrated/heic_image.HEIC
            ./Input/heic_image.HEIC
        """

        home.return_value = Path(self.temp_base.name)
        heic = copy_file(self.heic_file, self.input_folder)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(True)
        cleaner.set_keep_converted_files(True)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(cleaner.migrated_path.joinpath(heic.name).exists())
        self.assertTrue(heic.exists())
        self.assertTrue(self.output_folder.  # Kludge,  I just know the date on the file.  cheater, cheater
                        joinpath('2021').joinpath('10').joinpath('7').joinpath(f'{heic.stem}.jpg').exists())

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

        copy_file(self.jpg_file, self.input_folder.joinpath(DIR_SPEC))
        copy_file(self.jpg_file, self.output_folder.joinpath('test_instance_NoDate'))

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(cleaner.duplicate_path.joinpath(cleaner.no_date_base).joinpath(self.jpg_file.name).exists())
        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath(self.jpg_file.name).exists())

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

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)

        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath('file.jpg').exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(cleaner.no_date_base).joinpath('file.jpg').exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(cleaner.no_date_base).joinpath('file_0.jpg').exists())

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

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(cleaner.duplicate_path.joinpath(cleaner.no_date_base).joinpath('file.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath('file.jpg').exists())

        self.assertEqual(count_files(self.output_folder), 2)

    @patch('pathlib.Path.home')
    async def test_dup_jpg_files_no_dups(self, home):
        """
            ./Input/jpeg_image.jpg
            ./Input/1961/9/27/jpeg_image.jpg
            ./Input/CustomName/jpeg_image.jpg - ack
            ./Input/CustomName/1961/9/27/jpeg_image.jpg
            ./Input/nodate.jpg
            ./Input/CustomName/no_date.jpg - ack

            ./Output/1961/CustomName/jpeg_image.jpg
            ./Output/test_instance_NoDate/CustomName/no_date.jpg

        """

        home.return_value = Path(self.temp_base.name)
        no_date = copy_file(self.jpg_file, self.input_folder, new_name='no_date.jpg')
        set_date(no_date, None)
        copy_file(no_date, self.other_folder)

        internal_date = copy_file(self.jpg_file, self.input_folder)
        set_date(internal_date, DATE_SPEC)

        copy_file(no_date, self.input_folder.joinpath(DIR_SPEC), new_name=internal_date.name)
        copy_file(internal_date, self.other_folder, new_name=internal_date.name)
        copy_file(no_date, self.other_folder.joinpath(DIR_SPEC), new_name=internal_date.name)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(True)
        cleaner.set_keep_duplicates(False)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(self.other_folder.name).joinpath('no_date.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(str(DATE_SPEC.year)).
                        joinpath(self.other_folder.name).joinpath(internal_date.name).exists())

        self.assertEqual(count_files(self.output_folder), 2)
        self.assertEqual(count_files(self.input_folder), 6)

    @patch('pathlib.Path.home')
    async def test_dup_jpg_files_with_dups(self, home):
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
        no_date = create_image_file(self.input_folder.joinpath('no_date.jpg'), None)
        internal_date = copy_file(no_date, self.input_folder, new_name='jpeg_image.jpg')
        set_date(internal_date, DATE_SPEC)

        copy_file(no_date, self.other_folder)
        copy_file(no_date, self.input_folder.joinpath(DIR_SPEC), new_name=internal_date.name)
        copy_file(internal_date, self.other_folder, new_name=internal_date.name)
        copy_file(no_date, self.other_folder.joinpath(DIR_SPEC), new_name=internal_date.name)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(str(DATE_SPEC.year)).joinpath(self.other_folder.name).joinpath(internal_date.name).exists())

        self.assertTrue(cleaner.duplicate_path.joinpath(str(DATE_SPEC.year)).joinpath(self.other_folder.name).joinpath(internal_date.name).exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(DIR_SPEC).joinpath('jpeg_image.jpg').exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(DIR_SPEC).joinpath('jpeg_image_0.jpg').exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(cleaner.no_date_base).joinpath('no_date.jpg').exists())

        self.assertTrue(self.output_folder.joinpath(self.other_folder.name).joinpath('no_date.jpg').exists())

        self.assertEqual(count_files(self.output_folder), 6)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    async def test_dup_jpg_files_earlier_date(self, home):
        """
            Date storage is based on the earlier of folder dates is no dates on images

            ./Input/jpeg_image
            ./Input/1961/9/27/jpeg_image.jpg
            ./Input/1961/9/28/jpeg_image.jpg

            ./Output/1961/9/27/jpeg_image.jpg
            ./Output/test_instance_Duplicates/1961/9/28/jpeg_image.jpg
            ./Output/test_instance_Duplicates/test_instance_NoDate/jpeg_image.jpg
        """

        home.return_value = Path(self.temp_base.name)

        next_day = Path(str(DATE_SPEC.year)).joinpath(str(DATE_SPEC.month + 1)).joinpath(str(DATE_SPEC.day))

        create_image_file(self.input_folder, None)
        create_image_file(self.input_folder.joinpath(DIR_SPEC), None)
        create_image_file(self.input_folder.joinpath(next_day), None)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath('file.jpg').exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(next_day).joinpath('file.jpg').exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(cleaner.no_date_base).joinpath('file.jpg').exists())
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

        copy_file(self.jpg_file, self.input_folder.joinpath('custom1'))
        copy_file(self.jpg_file, self.output_folder.joinpath('custom2'))
        copy_file(self.jpg_file, self.input_folder.joinpath('custom3'))

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath('custom1').joinpath(self.jpg_file.name).exists())
        self.assertTrue(self.output_folder.joinpath('custom2').joinpath(self.jpg_file.name).exists())
        self.assertTrue(self.output_folder.joinpath('custom3').joinpath(self.jpg_file.name).exists())

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

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(self.output_folder.
                        joinpath(str(DATE_SPEC.year)).joinpath('custom3').joinpath('file.jpg').exists())
        self.assertTrue(self.output_folder.joinpath('custom2').joinpath('file.jpg').exists())
        self.assertTrue(self.output_folder.joinpath('custom1').joinpath('file.jpg').exists())

        self.assertEqual(count_files(self.output_folder), 3)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    async def test_dup_jpg_files_custom_date2(self, home):
        """
            ./Input/1961/9/27/jpeg_image.jpg
            # existing
            ./Output/1961/9/28/jpeg_image.jpg

            Result:
            ./Output/test_instance_Duplicates/1961/9/28/jpeg_image.jpg
            ./Output/1961/9/27/jpeg_image.jpg
        """

        home.return_value = Path(self.temp_base.name)
        no_date = copy_file(self.jpg_file, self.input_folder)
        set_date(no_date, None)

        next_day = Path(str(DATE_SPEC.year)).joinpath(str(DATE_SPEC.month)).joinpath(str(DATE_SPEC.day + 1))
        copy_file(no_date, self.output_folder.joinpath(DIR_SPEC))
        copy_file(no_date, self.input_folder.joinpath(next_day))
        no_date.unlink()

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath(no_date.name).exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(next_day).joinpath(no_date.name).exists())
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
        old = copy_file(self.jpg_file, self.input_folder.joinpath(DIR_SPEC))
        new = copy_file(self.jpg_file, self.output_folder.joinpath(next_day))
        set_date(old, DATE_SPEC)
        set_date(new, DATE_SPEC + timedelta(days=1))
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath(new.name).exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(next_day).joinpath(new.name).exists())
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
        old = copy_file(self.jpg_file, self.output_folder.joinpath(DIR_SPEC))
        new = copy_file(self.jpg_file, self.input_folder.joinpath(next_day))
        set_date(old, DATE_SPEC)
        set_date(new, DATE_SPEC + timedelta(days=1))
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath(new.name).exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(next_day).joinpath(new.name).exists())
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
        old = copy_file(self.jpg_file, self.output_folder.joinpath(DIR_SPEC))
        new = copy_file(self.jpg_file, self.input_folder.joinpath(next_day))
        set_date(old, DATE_SPEC)
        set_date(new, DATE_SPEC)
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath(new.name).exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(DIR_SPEC).joinpath(new.name).exists())
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

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath('file.jpg').exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(next_day).joinpath('file.jpg').exists())
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

        copy_file(self.jpg_file, self.output_folder.joinpath('custom'))
        copy_file(self.jpg_file, self.input_folder.joinpath(DIR_SPEC))
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath('custom').joinpath(self.jpg_file.name))
        self.assertTrue(cleaner.duplicate_path.joinpath(DIR_SPEC).joinpath(self.jpg_file.name).exists())
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
        no_date = copy_file(self.jpg_file, self.input_folder, new_name='nodate.txt')
        set_date(no_date, None)

        internal_date = copy_file(self.jpg_file, self.input_folder, new_name='internal_date.txt')
        set_date(internal_date, DATE_SPEC)

        copy_file(no_date, self.input_folder, new_name=f'{DATE_SPEC.strftime("%Y%m%d-010101")}.txt')
        copy_file(no_date, self.input_folder.joinpath(DIR_SPEC), new_name='struct_date.txt')
        copy_file(no_date, self.other_folder, new_name='no_date_custom.txt')
        copy_file(internal_date, self.other_folder, new_name='internal_date_custom.txt')
        copy_file(no_date, self.other_folder, new_name=f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.txt')
        copy_file(no_date, self.other_folder.joinpath(DIR_SPEC), new_name='struct_date_custom.txt')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.verbose = False
        await cleaner.run()

        self.assertFalse(cleaner.no_date_path.joinpath('nodate.txt').exists())
        self.assertFalse(self.output_folder.joinpath(DIR_SPEC).joinpath('internal_date.txt').exists())
        self.assertFalse(self.output_folder.joinpath(DIR_SPEC).
                         joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}.txt').exists())
        self.assertFalse(self.output_folder.joinpath(DIR_SPEC).
                         joinpath('struct_date.txt').exists())
        self.assertFalse(cleaner.no_date_path.
                         joinpath(self.other_folder.name).joinpath('no_date_custom.txt').exists())
        self.assertFalse(self.output_folder.joinpath(str(DATE_SPEC.year)).
                         joinpath(self.other_folder.name).joinpath('internal_date_custom.txt').exists())
        self.assertFalse(self.output_folder.joinpath(str(DATE_SPEC.year)).
                         joinpath(self.other_folder.name).joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.txt')
                         .exists())
        self.assertFalse(self.output_folder.joinpath(str(DATE_SPEC.year)).
                         joinpath(self.other_folder.name).joinpath('struct_date_custom.txt').exists())
        self.assertEqual(count_files(self.output_folder), 0)
        self.assertEqual(count_files(self.input_folder), 8)


class InitTest(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        super(InitTest, self).setUp()
        self.tempdir = tempfile.TemporaryDirectory()
        # print(f'\n{str(self)} - {self.tempdir.name}')

    def tearDown(self):
        self.tempdir.cleanup()
        super(InitTest, self).tearDown()

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
        self.assertTrue(app.verbose, "Verbose is not True")
        self.assertTrue(app.do_convert, "Conversion are not True")
        self.assertFalse(app.recreate, "Recreate is not false")
        self.assertTrue(app.do_convert)
        self.assertFalse(app.recreate)
        self.assertFalse(app.force_keep)
        self.assertFalse(app.keep_duplicates)
        self.assertFalse(app.keep_movie_clips)
        self.assertFalse(app.process_all_files)
        self.assertFalse(app.keep_converted_files)
        self.assertTrue(app.keep_original_files, "Keep original default is not True")
        self.assertListEqual(app.ignore_folders, [], "Ignore folders list is not empty")
        self.assertListEqual(app.bad_parents, [], "Name ignore list is not empty")
        self.assertEqual(app.progress, 0, "Progress has not been initialized")
        app.stop()

    @patch('pathlib.Path.home')
    async def test_run_path(self, home):
        home.return_value = Path(self.tempdir.name)

        expected_run_path = Path(Path.home().joinpath('.test_app_init_test'))
        app = ImageClean('test_app_init_test')
        app.verbose = False
        self.assertTrue(expected_run_path.exists())
        app.stop()

    @patch('pathlib.Path.home')
    async def test_save_and_restore(self, home):   # pylint: disable=too-many-statements

        home.return_value = Path(self.tempdir.name)

        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            app = ImageClean('test_app', restore=True)
            error_value = f'DEBUG:Cleaner:Restore attempt of'
            self.assertTrue(logs.output[len(logs.output) - 1].startswith(error_value), 'Restore Fails')
            # default value
            self.assertEqual(app.app_name, 'test_app', "Failed to set the app name")
            self.assertIsNotNone(app.conf_file, f'Config file {app.conf_file} is not set')
            self.assertEqual(app.input_folder, Path.home())
            self.assertEqual(app.input_folder, app.output_folder)
            self.assertTrue(app.verbose, "Verbose is not True")
            self.assertTrue(app.do_convert, "Conversion are not True")
            self.assertFalse(app.recreate, "Recreate is not false")
            self.assertTrue(app.do_convert)
            self.assertFalse(app.recreate)
            self.assertFalse(app.keep_duplicates)
            self.assertFalse(app.keep_movie_clips)
            self.assertFalse(app.keep_converted_files)
            self.assertTrue(app.keep_original_files, "Keep original default is not True")
            self.assertListEqual(app.ignore_folders, [], "Ignore folders list is not empty")
            self.assertListEqual(app.bad_parents, [], "Name ignore list is not empty")

            app.input_folder = Path('/input')
            app.output_folder = Path('/output')
            app.verbose = False
            app.do_convert = False
            app.set_recreate(True)
            app.set_keep_original_files(False)
            app.set_keep_duplicates(True)
            app.set_keep_movie_clips(True)
            app.set_keep_converted_files(True)
            app.add_ignore_folder(Path('/tmp/a'))
            app.add_ignore_folder(Path('/tmp/b'))
            self.assertFalse(app.add_ignore_folder(Path('/tmp/b')))
            app.add_bad_parents('homer')
            app.add_bad_parents('marge')
            self.assertFalse(app.add_bad_parents('marge'))

            app.save_config()
            app.stop()

        app = ImageClean('test_app', restore=True)
        app.verbose = False
        self.assertEqual(app.input_folder, Path('/input'))
        self.assertEqual(app.output_folder, Path('/output'))
        self.assertFalse(app.verbose, "Verbose is not True")
        self.assertFalse(app.do_convert, "Conversion are not True")
        self.assertTrue(app.recreate, "Recreate is not false")
        self.assertFalse(app.do_convert)
        self.assertTrue(app.recreate)
        self.assertTrue(app.keep_duplicates)
        self.assertTrue(app.keep_movie_clips)
        self.assertTrue(app.keep_converted_files)
        self.assertFalse(app.keep_original_files, "Keep original default is not True")
        self.assertListEqual(app.ignore_folders, [Path('/tmp/a'), Path('/tmp/b')], "Ignore folders list")
        self.assertListEqual(app.bad_parents, ['homer', 'marge'], "Name ignore list")
        app.stop()

    @patch('pathlib.Path.home')
    async def test_paranoid(self, home):
        home.return_value = Path(self.tempdir.name)
        app = ImageClean('test_app', restore=True)

        app.set_paranoid(True)
        self.assertTrue(app.keep_duplicates)
        self.assertTrue(app.keep_movie_clips)
        self.assertTrue(app.keep_converted_files)
        self.assertTrue(app.keep_original_files)

        app.set_paranoid(False)
        self.assertFalse(app.keep_duplicates)
        self.assertFalse(app.keep_movie_clips)
        self.assertFalse(app.keep_converted_files)
        self.assertFalse(app.keep_original_files)
        app.stop()

    @patch('pathlib.Path.home')
    async def test_prepare(self, home):
        home.return_value = Path(self.tempdir.name)
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
        self.assertEqual(len(app.ignore_folders), 4)
        self.assertEqual(len(app.bad_parents), 5)

        app.input_folder = app.output_folder
        app.set_recreate(True)
        with pytest.raises(AssertionError):  # Must assert if trying to recreate the input folder
            await app.run()

        app.set_recreate(False)
        await app.run()
        self.assertTrue(app.in_place, 'In place is not set')
        self.assertIsNone(app.duplicate_path)
        self.assertIsNone(app.migrated_path)
        self.assertIsNone(app.image_movies_path)
        self.assertIsNotNone(app.small_path)
        self.assertIsNotNone(app.no_date_path)

        app.set_keep_movie_clips(True)
        app.set_keep_duplicates(True)
        app.set_keep_converted_files(True)
        await app.run()
        self.assertIsNotNone(app.duplicate_path)
        self.assertIsNotNone(app.migrated_path)
        self.assertIsNotNone(app.image_movies_path)

        # Auto Cleanup in action
        self.assertFalse(app.duplicate_path.exists(), 'Duplicate path does not exist')
        self.assertFalse(app.migrated_path.exists(), 'Migrate path does not exist')
        self.assertFalse(app.image_movies_path.exists(), 'Movie path does not exist')
        self.assertFalse(app.no_date_path.exists(), 'No_Date path does not exist')
        self.assertFalse(app.small_path.exists(), 'Small path does not exist')

    @freeze_time("1961-09-27 19:21:34")
    @patch('pathlib.Path.home')
    async def test_prepare_rollover(self, home):
        home.return_value = Path(self.tempdir.name)
        output_folder = Path(self.tempdir.name).joinpath('output')
        input_folder = Path(self.tempdir.name).joinpath('input')

        os.mkdir(output_folder)
        os.mkdir(input_folder)

        app = ImageClean('test_app')
        app.output_folder = output_folder
        app.input_folder = input_folder
        app.set_recreate(True)
        app.verbose = False

        rolled_over = Path(f'{output_folder}_1961-09-27-19-21-34')
        self.assertFalse(rolled_over.exists())

        await app.run()
        self.assertTrue(rolled_over.exists())


class EdgeCaseTest(unittest.IsolatedAsyncioTestCase):  # pylint: disable=too-many-instance-attributes
    """
    These are test cases not covered in Actual Scenarios or Initialization
    """

    def tearDown(self):
        self.temp_base.cleanup()
        Cleaner.clear_caches()
        super(EdgeCaseTest, self).tearDown()

    def setUp(self):
        super(EdgeCaseTest, self).setUp()
        self.my_location = Path(os.path.dirname(__file__))
        self.app_name = 'test_instance'

        # Make basic folders
        self.temp_base = tempfile.TemporaryDirectory()
        self.output_folder = Path(self.temp_base.name).joinpath('Output')
        self.input_folder = Path(self.temp_base.name).joinpath('Input')

        os.mkdir(self.output_folder)
        os.mkdir(self.input_folder)

        self.small_file = self.my_location.joinpath('data').joinpath('small_image.jpg')
        self.heic_file = self.my_location.joinpath('data').joinpath('heic_image.HEIC')
        self.jpg_file = self.my_location.joinpath('data').joinpath('jpeg_image.jpg')

    @patch('pathlib.Path.home')
    async def test_read_only_input_forces_force_ro(self, home):
        home.return_value = Path(self.temp_base.name)
        orig = copy_file(self.jpg_file, self.input_folder)
        os.chmod(self.input_folder, mode=(stat.S_IREAD | stat.S_IEXEC))  # Set input to R/O
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.verbose = False
        await cleaner.run()
        self.assertTrue(orig.exists())

    @patch('pathlib.Path.home')
    async def test_bad_parents(self, home):
        home.return_value = Path(self.temp_base.name)

        orig = copy_file(self.jpg_file, self.input_folder.joinpath('Kathy_Nick'))
        set_date(orig, DATE_SPEC)
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.add_bad_parents('Kathy_Nick')
        cleaner.verbose = False
        await cleaner.run()

        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath(orig.name).exists())

    @patch('builtins.print')
    @patch('pathlib.Path.home')
    async def test_invalid(self, home, my_print):
        home.return_value = Path(self.temp_base.name)

        name = self.input_folder.joinpath('text.jpg')
        my_file = open(name, 'w+')
        my_file.close()  # Empty File
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.verbose = False
        await cleaner.run()
        my_print.assert_not_called()

        cleaner.verbose = True
        await cleaner.run()
        my_print.assert_called()

    @patch('Backend.image_clean.WARNING_FOLDER_SIZE', 2)
    @patch('pathlib.Path.home')
    async def test_audit_folders(self, home):
        home.return_value = Path(self.temp_base.name)

        one = copy_file(self.jpg_file, self.input_folder, new_name='one.jpg')
        set_date(one, datetime(1961, 9, 27))
        two = copy_file(one, self.input_folder, new_name='two.jpg')
        output_path = self.output_folder.joinpath('1961').joinpath('9').joinpath('27')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(True)
        cleaner.set_keep_movie_clips(True)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        await cleaner.run()
        self.assertTrue(one.exists())
        self.assertTrue(two.exists())
        self.assertTrue(output_path.joinpath(one.name).exists(), 'Image one processed')
        self.assertTrue(output_path.joinpath(two.name).exists(), 'Image two processed')
        self.assertEqual(len(cleaner.suspicious_folders), 0, 'No large folders')

    @patch('Backend.image_clean.WARNING_FOLDER_SIZE', 2)
    @patch('pathlib.Path.home')
    async def test_audit_folders_1(self, home):
        home.return_value = Path(self.temp_base.name)

        copy_file(self.jpg_file, self.output_folder.joinpath(DIR_SPEC), new_name='one.jpg')
        copy_file(self.jpg_file, self.output_folder.joinpath(DIR_SPEC), new_name='two.jpg')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.verbose = False
        await cleaner.run()
        self.assertEqual(len(cleaner.suspicious_folders), 0, 'No large folders')

    @patch('Backend.image_clean.WARNING_FOLDER_SIZE', 2)
    @patch('pathlib.Path.home')
    async def test_audit_folders_2(self, home):
        home.return_value = Path(self.temp_base.name)

        copy_file(self.jpg_file, self.output_folder.joinpath(DIR_SPEC), new_name='one.jpg')
        copy_file(self.jpg_file, self.output_folder.joinpath(DIR_SPEC), new_name='two.jpg')
        copy_file(self.jpg_file, self.output_folder.joinpath(DIR_SPEC), new_name='three.jpg')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.verbose = False
        await cleaner.run()
        self.assertEqual(len(cleaner.suspicious_folders), 1, 'Large folders')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
