import os
import stat
import time

import piexif
import sys
import tempfile
import unittest

from datetime import datetime, timedelta
from freezegun import freeze_time
from pathlib import Path
from shutil import copyfile
from typing import Union
from unittest import mock
from unittest.mock import patch

import pytest

from Backend.Cleaner import Cleaner, ImageCleaner, FileCleaner, FolderCleaner, file_cleaner
from Backend.ImageClean import NEW_FILE, EXACT_FILE, LESSER_FILE, GREATER_FILE, SMALL_FILE, WARNING_FOLDER_SIZE
from Backend.ImageClean import ImageClean

sys.path.append(f'{Path.home().joinpath("ImageClean")}')  # I got to figure out this hack,
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))

DATE_SPEC = datetime(1961, 9, 27)
DIR_SPEC = Path(str(DATE_SPEC.year)).joinpath(str(DATE_SPEC.month)).joinpath(str(DATE_SPEC.day))


def copy_file(in_file: Path, out_path: Path, new_name: str = None) -> Path:
    if not out_path.exists():
        os.makedirs(out_path)

    new_name = in_file.name if not new_name else new_name
    new = out_path.joinpath(new_name)
    copyfile(str(in_file), new)
    return new


def set_date(original_file: Path, new_date: Union[datetime, None]):
    """
    Given a physical file,  move the file to the input directory
    original_file:  The file to process
    new_date: date_string to put into file
    move_to_input: If set,  copy the file to this location.
    :return: None
    """
    exif_dict = piexif.load(str(original_file))
    if not new_date:
        if piexif.ImageIFD.DateTime in exif_dict['0th']:
            del (exif_dict['0th'][piexif.ImageIFD.DateTime])
        if piexif.ExifIFD.DateTimeOriginal in exif_dict['Exif']:
            del (exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal])
        if piexif.ExifIFD.DateTimeDigitized in exif_dict['Exif']:
            del (exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized])
    else:
        new_date = new_date.strftime("%Y:%m:%d %H:%M:%S")
        exif_dict['0th'][piexif.ImageIFD.DateTime] = new_date
        exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = new_date
        exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = new_date

    # Save changes
    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, str(original_file))


def count_files(path: Path):
    count = 0
    for _, _, files_list in os.walk(path):
        for file in files_list:
            count += 1
    return count


class ActualScenarioTest(unittest.TestCase):
    """
    Create real world scenerio's for testing.   This is perhaps not unit tests but system tests

    These tests cover all the duplicate scenerios


    """
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
    def test_restart_no_changes(self, home):
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

        duplicate_path_base = self.input_folder.joinpath(f'{self.app_name}_Duplicates')
        image_movies_path_base = self.input_folder.joinpath(f'{self.app_name}_ImageMovies')
        migrated_path_base = self.input_folder.joinpath(f'{self.app_name}_Migrated')
        no_date_base = self.input_folder.joinpath(f'{self.app_name}_NoDate')
        small_base = self.input_folder.joinpath(f'{self.app_name}_Small')

        no_date = copy_file(self.jpg_file, no_date_base, new_name='no_date.jpg')
        set_date(no_date, None)

        internal_date = copy_file(self.jpg_file, self.input_folder.joinpath(DIR_SPEC), new_name='internal_date.jpg')
        set_date(internal_date, DATE_SPEC)

        filename_date = copy_file(no_date,
                                  self.input_folder.joinpath(DIR_SPEC),
                                  new_name=f'{DATE_SPEC.strftime("%Y%m%d-010101")}.jpg')
        struct_date = copy_file(no_date,
                                self.input_folder.joinpath(DIR_SPEC),
                                new_name='struct_date.jpg')
        no_date_custom = copy_file(no_date,
                                   self.input_folder.joinpath(self.other_folder),
                                   new_name='no_date_custom.jpg')
        date_custom = copy_file(internal_date,
                                self.input_folder.joinpath(str(DATE_SPEC.year)).joinpath(self.other_folder),
                                new_name='internal_date_custom.jpg')
        name_custom = copy_file(no_date,
                                self.input_folder.joinpath(str(DATE_SPEC.year)).joinpath(self.other_folder),
                                new_name=f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.jpg')
        struct_custom = copy_file(no_date,
                                  self.input_folder.joinpath(str(DATE_SPEC.year)).joinpath(self.other_folder),
                                  new_name='struct_date_custom.jpg')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.input_folder)
        cleaner.set_keep_original_files(False)
        cleaner.verbose = False
        cleaner.run()

        self.assertTrue(no_date.exists())
        self.assertTrue(internal_date.exists())
        self.assertTrue(filename_date.exists())
        self.assertTrue(struct_date.exists())
        self.assertTrue(no_date_custom.exists())
        self.assertTrue(date_custom.exists())
        self.assertTrue(name_custom.exists())
        self.assertTrue(struct_custom.exists())

    @patch('pathlib.Path.home')
    def test_jpg_files(self, home):
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
        no_date = copy_file(self.jpg_file, self.input_folder, new_name='nodate.jpg')
        set_date(no_date, None)

        internal_date = copy_file(self.jpg_file, self.input_folder, new_name='internal_date.jpg')
        set_date(internal_date, DATE_SPEC)

        copy_file(no_date, self.input_folder, new_name=f'{DATE_SPEC.strftime("%Y%m%d-010101")}.jpg')
        copy_file(no_date, self.input_folder.joinpath(DIR_SPEC), new_name='struct_date.jpg')
        copy_file(no_date, self.other_folder, new_name='no_date_custom.jpg')
        copy_file(internal_date, self.other_folder, new_name='internal_date_custom.jpg')
        copy_file(no_date, self.other_folder, new_name=f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.jpg')
        copy_file(no_date, self.other_folder.joinpath(DIR_SPEC), new_name='struct_date_custom.jpg')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.verbose = False
        cleaner.run()

        self.assertTrue(cleaner.no_date_path.joinpath('nodate.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath('internal_date.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).
                        joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).
                        joinpath('struct_date.jpg').exists())
        self.assertTrue(cleaner.no_date_path.
                        joinpath(self.other_folder.name).joinpath('no_date_custom.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(str(DATE_SPEC.year)).
                        joinpath(self.other_folder.name).joinpath('internal_date_custom.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(str(DATE_SPEC.year)).
                        joinpath(self.other_folder.name).joinpath(f'{DATE_SPEC.strftime("%Y%m%d-010101")}_custom.jpg')
                        .exists())
        self.assertTrue(self.output_folder.joinpath(str(DATE_SPEC.year)).
                        joinpath(self.other_folder.name).joinpath('struct_date_custom.jpg').exists())

    @patch('pathlib.Path.home')
    def test_small_files(self, home):
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
        cleaner.run()

        self.assertTrue(cleaner.small_path.joinpath('nodate.jpg').exists())
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
    def test_mov_files_keep(self, home):
        """
        """

        home.return_value = Path(self.temp_base.name)
        no_date_mov = copy_file(self.jpg_file, self.input_folder, new_name='no_date.mov')
        set_date(no_date_mov, None)
        copy_file(no_date_mov, self.input_folder, new_name='no_date.jpg')
        copy_file(no_date_mov, self.input_folder, new_name='other_no_date.mov')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_movie_clips(True)
        cleaner.set_keep_original_files(True)
        cleaner.verbose = False
        cleaner.run()

        self.assertTrue(cleaner.no_date_path.joinpath('no_date.jpg').exists())
        self.assertTrue(cleaner.image_movies_path.joinpath('no_date.mov').exists())
        self.assertTrue(cleaner.no_date_path.joinpath('other_no_date.mov').exists())
        self.assertEqual(count_files(self.input_folder), 3)
        self.assertEqual(count_files(self.output_folder), 3)

    @patch('pathlib.Path.home')
    def test_mov_files_no_keep(self, home):
        """
        """

        home.return_value = Path(self.temp_base.name)
        no_date_mov = copy_file(self.jpg_file, self.input_folder, new_name='no_date.mov')
        set_date(no_date_mov, None)
        copy_file(no_date_mov, self.input_folder, new_name='no_date.jpg')
        copy_file(no_date_mov, self.input_folder, new_name='other_no_date.mov')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_movie_clips(False)
        cleaner.set_keep_original_files(False)
        cleaner.verbose = False
        cleaner.run()

        self.assertTrue(cleaner.no_date_path.joinpath('no_date.jpg').exists())
        self.assertTrue(cleaner.no_date_path.joinpath('other_no_date.mov').exists())
        self.assertEqual(count_files(self.input_folder), 0)
        self.assertEqual(count_files(self.output_folder), 2)

    @patch('pathlib.Path.home')
    def test_heic_files(self, home):
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
        cleaner.run()

        self.assertTrue(cleaner.migrated_path.joinpath(heic.name).exists())
        self.assertTrue(heic.exists())
        self.assertTrue(self.output_folder.  # Kludge,  I just know the date on the file.  cheater, cheater
                        joinpath('2021').joinpath('10').joinpath('7').joinpath(f'{heic.stem}.jpg').exists())

    @patch('pathlib.Path.home')
    def test_dup_jpg_new_date(self, home):
        """
            ./Input/1961/9/27/jpeg_image.jpg
            ./Output/test_instance_NoDate/no_date.jpg

            after run
            ./Output/1961/9/27/jpeg_image.jpg
            ./Output/test_instance_Duplicates/no_date.jpg

        """

        home.return_value = Path(self.temp_base.name)

        copy_file(self.jpg_file, self.input_folder.joinpath(DIR_SPEC))
        copy_file(self.jpg_file, self.output_folder.joinpath('test_instance_NoDate'))

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        cleaner.run()

        self.assertTrue(cleaner.duplicate_path.joinpath(self.jpg_file.name).exists())
        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath(self.jpg_file.name).exists())

        self.assertEqual(count_files(self.output_folder), 2)

    @patch('pathlib.Path.home')
    def test_dup_jpg_old_date(self, home):
        """
            ./Input/1961/9/27/jpeg_image.jpg
            ./Output/test_instance_NoDate/no_date.jpg

            after run
            ./Output/1961/9/27/jpeg_image.jpg
            ./Output/test_instance_Duplicates/no_date.jpg

        """

        home.return_value = Path(self.temp_base.name)

        copy_file(self.jpg_file, self.output_folder.joinpath(DIR_SPEC))
        copy_file(self.jpg_file, self.input_folder)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        cleaner.run()

        self.assertTrue(cleaner.duplicate_path.joinpath(self.jpg_file.name).exists())
        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath(self.jpg_file.name).exists())

        self.assertEqual(count_files(self.output_folder), 2)

    @patch('pathlib.Path.home')
    def test_dup_jpg_files_no_dups(self, home):
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
        cleaner.run()

        self.assertTrue(cleaner.no_date_path.joinpath(self.other_folder.name).joinpath('no_date.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(str(DATE_SPEC.year)).
                        joinpath(self.other_folder.name).joinpath(internal_date.name).exists())

        self.assertEqual(count_files(self.output_folder), 2)
        self.assertEqual(count_files(self.input_folder), 6)

    @patch('pathlib.Path.home')
    def test_dup_jpg_files_with_dups(self, home):
        """
            ./Input/jpeg_image.jpg
            ./Input/1961/9/27/jpeg_image.jpg
            ./Input/CustomName/jpeg_image.jpg - ack
            ./Input/CustomName/1961/9/27/jpeg_image.jpg

            ./Input/nodate.jpg
            ./Input/CustomName/no_date.jpg - ack

            ./Output/1961/CustomName/jpeg_image.jpg
            ./Output/test_instance_NoDate/CustomName/no_date.jpg
            ./Output/test_instance_Duplicates/no_date.jpg
            ./Output/test_instance_Duplicates/1961/9/27/jpeg_image.jpg
            ./Output/test_instance_Duplicates/1961/CustomName/jpeg_image.jpg
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
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        cleaner.run()

        self.assertTrue(cleaner.no_date_path.joinpath(self.other_folder.name).joinpath('no_date.jpg').exists())
        self.assertTrue(self.output_folder.joinpath(str(DATE_SPEC.year)).
                        joinpath(self.other_folder.name).joinpath(internal_date.name).exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(str(DATE_SPEC.year)).
                        joinpath(self.other_folder.name).joinpath(internal_date.name).exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(str(DATE_SPEC.year)).
                        joinpath(self.other_folder.name).joinpath(internal_date.name).exists())
        self.assertTrue(cleaner.duplicate_path.joinpath('no_date.jpg').exists())
        self.assertEqual(count_files(self.output_folder), 5)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    def test_dup_jpg_files_earlier_date(self, home):
        """
            Date storage is baed on the earlier of dates

            ./Input/jpeg_image  - with nodate
            ./Input/1961/9/27/jpeg_image.jpg
            ./Input/1961/9/28/jpeg_image.jpg

            ./Output/1961/9/27/jpeg_image.jpg
            ./Output/test_instance_Duplicates/1961/9/28/jpeg_image.jpg
        """

        home.return_value = Path(self.temp_base.name)
        no_date = copy_file(self.jpg_file, self.input_folder)
        set_date(no_date, None)

        next_day = Path(str(DATE_SPEC.year)).joinpath(str(DATE_SPEC.month + 1)).joinpath(str(DATE_SPEC.day))

        copy_file(no_date, self.input_folder.joinpath(DIR_SPEC))
        copy_file(no_date, self.input_folder.joinpath(next_day))

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        cleaner.run()

        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath(no_date.name).exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(next_day).joinpath(no_date.name).exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(no_date.name).exists())
        self.assertEqual(count_files(self.output_folder), 3)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    def test_dup_jpg_files_custom_no_dates(self, home):
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
        cleaner.run()

        self.assertTrue(self.output_folder.joinpath('custom1').joinpath(self.jpg_file.name).exists())
        self.assertTrue(self.output_folder.joinpath('custom2').joinpath(self.jpg_file.name).exists())
        self.assertTrue(self.output_folder.joinpath('custom3').joinpath(self.jpg_file.name).exists())

        self.assertEqual(count_files(self.output_folder), 3)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    def test_dup_jpg_files_custom_with_date(self, home):
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

        copy_file(self.jpg_file, self.input_folder.joinpath('custom1'))
        copy_file(self.jpg_file, self.output_folder.joinpath('custom2'))
        custom3 = copy_file(self.jpg_file, self.input_folder.joinpath('custom3'))
        set_date(custom3, DATE_SPEC)

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        cleaner.run()

        self.assertTrue(self.output_folder.
                        joinpath(str(DATE_SPEC.year)).joinpath('custom3').joinpath(self.jpg_file.name).exists())
        self.assertTrue(self.output_folder.joinpath('custom2').joinpath(self.jpg_file.name).exists())
        self.assertTrue(cleaner.duplicate_path.joinpath('custom1').joinpath(self.jpg_file.name).exists())

        self.assertEqual(count_files(self.output_folder), 3)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    def test_dup_jpg_files_custom_date2(self, home):
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
        cleaner.run()

        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath(no_date.name).exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(next_day).joinpath(no_date.name).exists())
        self.assertEqual(count_files(self.output_folder), 2)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    def test_dup_jpg_files_internal_date1(self, home):
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
        cleaner.run()

        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath(new.name).exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(next_day).joinpath(new.name).exists())
        self.assertEqual(count_files(self.output_folder), 2)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    def test_dup_jpg_files_internal_date2(self, home):
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
        cleaner.run()

        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath(new.name).exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(next_day).joinpath(new.name).exists())
        self.assertEqual(count_files(self.output_folder), 2)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    def test_dup_jpg_files_internal_date3(self, home):
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
        cleaner.run()

        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath(new.name).exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(DIR_SPEC).joinpath(new.name).exists())
        self.assertEqual(count_files(self.output_folder), 2)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    def test_dup_jpg_files_internal_date4(self, home):
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
        set_date(new, DATE_SPEC)
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.set_keep_duplicates(True)
        cleaner.verbose = False
        cleaner.run()

        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath(new.name).exists())
        self.assertTrue(cleaner.duplicate_path.joinpath(DIR_SPEC).joinpath(new.name).exists())
        self.assertEqual(count_files(self.output_folder), 2)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    def test_dup_jpg_files_custom_over_date(self, home):
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
        cleaner.run()

        self.assertTrue(self.output_folder.joinpath('custom').joinpath(self.jpg_file.name))
        self.assertTrue(cleaner.duplicate_path.joinpath(DIR_SPEC).joinpath(self.jpg_file.name).exists())
        self.assertEqual(count_files(self.output_folder), 2)
        self.assertEqual(count_files(self.input_folder), 0)

    @patch('pathlib.Path.home')
    def test_txt_files(self, home):
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
        cleaner.run()

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


class InitTest(unittest.TestCase):

    def setUp(self):
        super(InitTest, self).setUp()
        self.tempdir = tempfile.TemporaryDirectory()
        # print(f'\n{str(self)} - {self.tempdir.name}')

    def tearDown(self):
        self.tempdir.cleanup()
        super(InitTest, self).tearDown()

    @patch('pathlib.Path.home')
    def test_init(self, home):
        """
        Basic test for initialized values
        :return:
        """
        home.return_value = Path(self.tempdir.name)
        self.app = ImageClean('test_app')
        self.assertEqual(self.app.app_name, 'test_app', "Failed to set the app name")
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
        self.app.stop()

    @patch('pathlib.Path.home')
    def test_run_path(self, home):
        home.return_value = Path(self.tempdir.name)

        expected_run_path = Path(Path.home().joinpath('.test_app_init_test'))
        f = ImageClean('test_app_init_test')
        f.verbose = False
        self.assertTrue(expected_run_path.exists())
        f.stop()

    @patch('pathlib.Path.home')
    def test_save_and_restore(self, home):
        home.return_value = Path(self.tempdir.name)

        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            self.app = ImageClean('test_app', restore=True)
            error_value = f'DEBUG:Cleaner:Restore attempt of'
            self.assertTrue(logs.output[len(logs.output) - 1].startswith(error_value), 'Restore Fails')
            # default value
            self.assertEqual(self.app.app_name, 'test_app', "Failed to set the app name")
            self.assertIsNotNone(self.app.conf_file, f'Config file {self.app.conf_file} is not set')
            self.assertEqual(self.app.input_folder, Path.home())
            self.assertEqual(self.app.input_folder, self.app.output_folder)
            self.assertTrue(self.app.verbose, "Verbose is not True")
            self.assertTrue(self.app.do_convert, "Conversion are not True")
            self.assertFalse(self.app.recreate, "Recreate is not false")
            self.assertTrue(self.app.do_convert)
            self.assertFalse(self.app.recreate)
            self.assertFalse(self.app.keep_duplicates)
            self.assertFalse(self.app.keep_movie_clips)
            self.assertFalse(self.app.keep_converted_files)
            self.assertTrue(self.app.keep_original_files, "Keep original default is not True")
            self.assertListEqual(self.app.ignore_folders, [], "Ignore folders list is not empty")
            self.assertListEqual(self.app.bad_parents, [], "Name ignore list is not empty")

            self.app.input_folder = Path('/input')
            self.app.output_folder = Path('/output')
            self.app.verbose = False
            self.app.do_convert = False
            self.app.set_recreate(True)
            self.app.set_keep_original_files(False)
            self.app.set_keep_duplicates(True)
            self.app.set_keep_movie_clips(True)
            self.app.set_keep_converted_files(True)
            self.app.add_ignore_folder(Path('/tmp/a'))
            self.app.add_ignore_folder(Path('/tmp/b'))
            self.assertFalse(self.app.add_ignore_folder(Path('/tmp/b')))
            self.app.add_bad_parents('homer')
            self.app.add_bad_parents('marge')
            self.assertFalse(self.app.add_bad_parents('marge'))

            self.app.save_config()
            self.app.stop()

        self.app = ImageClean('test_app', restore=True)
        self.app.verbose = False
        self.assertEqual(self.app.input_folder, Path('/input'))
        self.assertEqual(self.app.output_folder, Path('/output'))
        self.assertFalse(self.app.verbose, "Verbose is not True")
        self.assertFalse(self.app.do_convert, "Conversion are not True")
        self.assertTrue(self.app.recreate, "Recreate is not false")
        self.assertFalse(self.app.do_convert)
        self.assertTrue(self.app.recreate)
        self.assertTrue(self.app.keep_duplicates)
        self.assertTrue(self.app.keep_movie_clips)
        self.assertTrue(self.app.keep_converted_files)
        self.assertFalse(self.app.keep_original_files, "Keep original default is not True")
        self.assertListEqual(self.app.ignore_folders, [Path('/tmp/a'), Path('/tmp/b')], "Ignore folders list")
        self.assertListEqual(self.app.bad_parents, ['homer', 'marge'], "Name ignore list")
        self.app.stop()

    @patch('pathlib.Path.home')
    def test_paranoid(self, home):
        home.return_value = Path(self.tempdir.name)
        self.app = ImageClean('test_app', restore=True)

        self.app.set_paranoid(True)
        self.assertTrue(self.app.keep_duplicates)
        self.assertTrue(self.app.keep_movie_clips)
        self.assertTrue(self.app.keep_converted_files)
        self.assertTrue(self.app.keep_original_files)

        self.app.set_paranoid(False)
        self.assertFalse(self.app.keep_duplicates)
        self.assertFalse(self.app.keep_movie_clips)
        self.assertFalse(self.app.keep_converted_files)
        self.assertFalse(self.app.keep_original_files)
        self.app.stop()

    @patch('pathlib.Path.home')
    def test_prepare(self, home):
        home.return_value = Path(self.tempdir.name)
        output_folder = Path(self.tempdir.name).joinpath('output')
        input_folder = Path(self.tempdir.name).joinpath('input')

        os.mkdir(output_folder)
        os.mkdir(input_folder)

        self.app = ImageClean('test_app')
        self.app.output_folder = output_folder
        self.app.input_folder = input_folder
        self.app.verbose = False

        os.chmod(output_folder, mode=stat.S_IREAD)  # set to R/O
        with pytest.raises(AssertionError):  # Must assert with R/O output folder
            self.app.run()

        os.chmod(output_folder, mode=stat.S_IRWXU)  # Rest output
        os.chmod(input_folder, mode=stat.S_IREAD)  # Set input to R/O

        self.app.run()
        self.assertTrue(self.app.force_keep, 'Force Keep is set')
        self.assertEqual(len(self.app.ignore_folders), 4)
        self.assertEqual(len(self.app.bad_parents), 5)

        self.app.input_folder = self.app.output_folder
        self.app.set_recreate(True)
        with pytest.raises(AssertionError):  # Must assert if trying to recreate the input folder
            self.app.run()

        self.app.set_recreate(False)
        self.app.run()
        self.assertTrue(self.app.in_place, 'In place is not set')
        self.assertIsNone(self.app.duplicate_path)
        self.assertIsNone(self.app.migrated_path)
        self.assertIsNone(self.app.image_movies_path)
        self.assertIsNotNone(self.app.small_path)
        self.assertIsNotNone(self.app.no_date_path)

        self.app.set_keep_movie_clips(True)
        self.app.set_keep_duplicates(True)
        self.app.set_keep_converted_files(True)
        self.app.run()
        self.assertIsNotNone(self.app.duplicate_path)
        self.assertIsNotNone(self.app.migrated_path)
        self.assertIsNotNone(self.app.image_movies_path)

        # Auto Cleanup in action
        self.assertFalse(self.app.duplicate_path.exists(), 'Duplicate path does not exist')
        self.assertFalse(self.app.migrated_path.exists(), 'Migrate path does not exist')
        self.assertFalse(self.app.image_movies_path.exists(), 'Movie path does not exist')
        self.assertFalse(self.app.no_date_path.exists(), 'No_Date path does not exist')
        self.assertFalse(self.app.small_path.exists(), 'Small path does not exist')

    @freeze_time("1961-09-27 19:21:34")
    @patch('pathlib.Path.home')
    def test_prepare_rollover(self, home):
        home.return_value = Path(self.tempdir.name)
        output_folder = Path(self.tempdir.name).joinpath('output')
        input_folder = Path(self.tempdir.name).joinpath('input')

        os.mkdir(output_folder)
        os.mkdir(input_folder)

        self.app = ImageClean('test_app')
        self.app.output_folder = output_folder
        self.app.input_folder = input_folder
        self.app.set_recreate(True)
        self.app.verbose = False

        rolled_over = Path(f'{output_folder}_1961-09-27-19-21-34')
        self.assertFalse(rolled_over.exists())

        self.app.run()
        self.assertTrue(rolled_over.exists())


class EdgeCaseTest(unittest.TestCase):
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
    def test_RO_input_forces_force_ro(self, home):
        home.return_value = Path(self.temp_base.name)
        orig = copy_file(self.jpg_file, self.input_folder)
        os.chmod(self.input_folder, mode=(stat.S_IREAD | stat.S_IEXEC))  # Set input to R/O
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.set_keep_original_files(False)
        cleaner.verbose = False
        cleaner.run()
        self.assertTrue(orig.exists())

    @patch('pathlib.Path.home')
    def test_bad_parents(self, home):
        home.return_value = Path(self.temp_base.name)

        orig = copy_file(self.jpg_file, self.input_folder.joinpath('Kathy_Nick'))
        set_date(orig, DATE_SPEC)
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.add_bad_parents('Kathy_Nick')
        cleaner.verbose = False
        cleaner.run()

        self.assertTrue(self.output_folder.joinpath(DIR_SPEC).joinpath(orig.name).exists())

    @patch('builtins.print')
    @patch('pathlib.Path.home')
    def test_invalid(self, home, my_print):
        home.return_value = Path(self.temp_base.name)

        name = self.input_folder.joinpath('text.jpg')
        f = open(name, 'w+')
        f.close()  # Empty File
        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.verbose = False
        cleaner.run()
        my_print.assert_not_called()

        cleaner.verbose = True
        cleaner.run()
        my_print.assert_called()

    @patch('Backend.ImageClean.WARNING_FOLDER_SIZE', 2)
    @patch('pathlib.Path.home')
    def test_audit_folders(self, home):
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
        cleaner.run()
        self.assertTrue(one.exists())
        self.assertTrue(two.exists())
        self.assertTrue(output_path.joinpath(one.name).exists(), 'Image one processed')
        self.assertTrue(output_path.joinpath(two.name).exists(), 'Image two processed')
        self.assertEqual(len(cleaner.suspicious_folders), 0, 'No large folders')

    @patch('Backend.ImageClean.WARNING_FOLDER_SIZE', 2)
    @patch('pathlib.Path.home')
    def test_audit_folders_1(self, home):
        home.return_value = Path(self.temp_base.name)

        copy_file(self.jpg_file, self.output_folder.joinpath(DIR_SPEC), new_name='one.jpg')
        copy_file(self.jpg_file, self.output_folder.joinpath(DIR_SPEC), new_name='two.jpg')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.verbose = False
        cleaner.run()
        self.assertEqual(len(cleaner.suspicious_folders), 0, 'No large folders')

    @patch('Backend.ImageClean.WARNING_FOLDER_SIZE', 2)
    @patch('pathlib.Path.home')
    def test_audit_folders_2(self, home):
        home.return_value = Path(self.temp_base.name)

        copy_file(self.jpg_file, self.output_folder.joinpath(DIR_SPEC), new_name='one.jpg')
        copy_file(self.jpg_file, self.output_folder.joinpath(DIR_SPEC), new_name='two.jpg')
        copy_file(self.jpg_file, self.output_folder.joinpath(DIR_SPEC), new_name='three.jpg')

        cleaner = ImageClean(self.app_name, input=self.input_folder, output=self.output_folder)
        cleaner.verbose = False
        cleaner.run()
        self.assertEqual(len(cleaner.suspicious_folders), 1, 'Large folders')

if __name__ == '__main__':  # pragma: no cover
    unittest.main()