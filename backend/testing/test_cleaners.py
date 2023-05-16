# pylint Overrides
# pylint: disable=duplicate-code
# pylint: disable=line-too-long
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=too-many-public-methods

"""
Test cases in this file process actual images,  I was going to MOCK everything but in the end I opted to exercise the
imaging frameworks.   There files are used,  a standard jpg,  a thumbnail and a HEIC file

"""
import os
import platform
import tempfile

import unittest

from datetime import datetime, timedelta
from filecmp import cmp
from pathlib import Path
from unittest.mock import patch
from unittest import TestCase

import piexif

# pylint: disable=import-error
from backend.cleaner import ImageCleaner, CleanerBase, FileCleaner, \
    make_cleaner_object, output_files, PICTURE_FILES, MOVIE_FILES
from Utilities.test_utilities import copy_file, create_file, create_image_file, set_date, count_files, DATE_SPEC


class CleanerUtilsTest(unittest.TestCase):
    def setUp(self):
        super().setUp()
        CleanerBase.clear_caches()

    def test_objects(self):
        for image_type in PICTURE_FILES:
            my_object = make_cleaner_object(Path(f'/fake/foo{image_type}'))
            self.assertEqual('ImageCleaner', my_object.__class__.__name__,
                             f'Expected ImageCleaner Object - got {my_object.__class__.__name__}')

        for image_type in MOVIE_FILES:
            my_object = make_cleaner_object(Path(f'/fake/foo{image_type}'))
            self.assertEqual('ImageCleaner', my_object.__class__.__name__,
                             f'{my_object.path} Expected ImageCleaner Object - got {my_object.__class__.__name__}')

        my_object = make_cleaner_object(Path('/fake/foo.text'))
        self.assertEqual('FileCleaner', my_object.__class__.__name__,
                         f'{my_object.path} Expected FileCleaner Object - got {my_object.__class__.__name__}')


class CleanersInitTest(TestCase):
    """
    Test out the basic init avoided class Cleaners for setup
    """

    def setUp(self):
        super().setUp()
        CleanerBase.clear_caches()

    def test_null_values(self):
        # pylint: disable=protected-access
        new_obj = CleanerBase(Path('/fake_parent/fake_dir/fake.file'))
        self.assertEqual(new_obj.path, Path('/fake_parent/fake_dir/fake.file'))
        self.assertIsNone(new_obj._date)

    def test_date(self):
        test_obj = CleanerBase(Path('/does/not/need.to_exist'))
        self.assertIsNone(test_obj.date)
        now = datetime.now()
        test_obj._date = now  # pylint: disable=protected-access
        self.assertEqual(test_obj.date, now)


class Cleaners(TestCase):

    def setUp(self):
        super().setUp()
        # define standard files

        # Make basic folders
        self.temp_base = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.output_folder = Path(self.temp_base.name).joinpath('Output')
        self.input_folder = Path(self.temp_base.name).joinpath('Input')
        os.mkdir(self.output_folder)
        os.mkdir(self.input_folder)

        CleanerBase.clear_caches()

        self.migration_base = Path(self.temp_base.name)
        self.run_base = self.migration_base

    def tearDown(self):
        self.temp_base.cleanup()
        super().tearDown()


class CleanerTests(Cleaners):

    def setUp(self):
        super().setUp()
        self.file1 = CleanerBase(create_file(self.input_folder.joinpath('a.file')))
        self.file2 = CleanerBase(create_file(self.input_folder.joinpath('b.file')))

    def test_default_compare(self):
        self.assertFalse(self.file1 > self.file2)
        self.assertFalse(self.file2 < self.file1)
        self.assertFalse(self.file1 < self.file2)
        self.assertFalse(self.file2 > self.file1)

    def test_no_convert(self):
        self.assertEqual(self.file1.convert(None, None).path, self.file1.path)

    def test_notimplemented(self):
        self.assertFalse(self.file1.is_small)

    def test_registry_key(self):
        original_path = self.file1.path
        expected_key = self.file1.path.stem.upper()
        self.assertEqual(expected_key, self.file1.registry_key)

        self.file1.path = Path('something_else')
        self.assertEqual(expected_key, self.file1.registry_key, 'Since it is cached.')

        self.file1 = CleanerBase(original_path.parent.joinpath(f'{original_path.stem}_1{original_path.suffix}'))
        self.assertEqual(expected_key, self.file1.registry_key)

        self.file1 = CleanerBase(original_path.joinpath(f'{original_path.stem}_99{original_path.suffix}'))
        self.assertEqual(expected_key, self.file1.registry_key)

        self.file1 = CleanerBase(original_path.parent.joinpath(f'{original_path.stem}_100{original_path.suffix}'))
        self.assertNotEqual(expected_key, self.file1.registry_key)

        self.file1 = CleanerBase(original_path.parent.joinpath(f'{original_path.stem}1{original_path.suffix}'))
        self.assertNotEqual(expected_key, self.file1.registry_key)

        self.file1 = CleanerBase(original_path.parent.joinpath(f'{original_path.stem}-1{original_path.suffix}'))
        self.assertNotEqual(expected_key, self.file1.registry_key)


# pylint disable=too-many-public-methods
class ImageCleanerTests(Cleaners):

    def setUp(self):
        """
        No need to tearDown since super will clean up input directory
        :return:
        """
        super().setUp()

        self.small_obj = ImageCleaner(
            create_image_file(Path(self.temp_base.name).joinpath('small_image.jpg'), None, small=True))

        my_location = Path(os.path.dirname(__file__))
        self.heic_obj = ImageCleaner(
            copy_file(my_location.joinpath('data').joinpath('heic_image.HEIC'),
                      Path(self.temp_base.name).joinpath('heic')))

        self.jpg_obj = ImageCleaner(
            create_image_file(Path(self.temp_base.name).joinpath('jpeg_image.jpg'), None))

    def test_date_no_date(self):
        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            date_value = self.jpg_obj.get_date_from_image()
            self.assertEqual(logs.output[0], f'DEBUG:Cleaner:Could not find a date in {self.jpg_obj.path}')
            self.assertIsNone(date_value, 'Image time should be None')

    def test_date_date(self):
        image_time = datetime.now() - timedelta(days=1)
        set_date(self.jpg_obj.path, image_time)
        new_time = self.jpg_obj.get_date_from_image()
        self.assertEqual(new_time.year, image_time.year, 'Matching year')
        self.assertEqual(new_time.month, image_time.month, 'Matching month')
        self.assertEqual(new_time.day, image_time.day, 'Matching day')
        # don't care about anything else

        invalid_image = ImageCleaner(create_file(self.input_folder.joinpath('invalid.jpg'), ))
        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            _ = invalid_image.get_date_from_image()
            self.assertEqual(logs.output[0], f'DEBUG:Cleaner:Failed to load {invalid_image.path} - Invalid JPEG/TIFF')

        os.unlink(invalid_image.path)
        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            _ = invalid_image.get_date_from_image()
            self.assertEqual(logs.output[0], f'DEBUG:Cleaner:Failed to load {invalid_image.path} - File not Found')

    def test_os_image_error(self):
        image_error = ImageCleaner(Path('fake_faker_fakest.jpg'))
        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            image_error.open_image()
            self.assertTrue(logs.output[0].startswith('DEBUG:Cleaner:open_image OSError'),  image_error.path.name)

    def test_image_data(self):
        # pylint: disable=protected-access
        self.assertListEqual(self.jpg_obj._image_data, [], "Image data should be empty")
        _ = self.jpg_obj.image_data
        self.assertNotEqual(self.jpg_obj._image_data, [], "Image data has been cached")

    def test_image_compare(self):
        """
        Test ==, !=, < and >
        """

        # test1 -> Same File - Different paths
        copy_obj = ImageCleaner(copy_file(self.jpg_obj.path, self.input_folder))
        self.assertTrue(copy_obj == self.jpg_obj, 'Files are the same/name and size')

    def test_image_compare2(self):
        # test2 -> Same File,  Different names
        clone_obj = ImageCleaner(
            copy_file(self.jpg_obj.path, self.jpg_obj.path.parent, new_name='new_name.jpg'))  # make a copy
        self.assertTrue(self.jpg_obj == clone_obj, 'Files are still the same')

    def test_image_compare3(self):
        # test3 -> Add a timestamp,   should still be ==
        clone_obj = ImageCleaner(
            copy_file(self.jpg_obj.path, self.jpg_obj.path.parent, new_name='new_name.jpg'))  # make a copy

        image_time = datetime.now()
        set_date(clone_obj.path, image_time)
        self.assertTrue(self.jpg_obj == clone_obj, 'Files are still the same, regardless of dates')

    def test_image_compare4(self):
        # test4 -> make sure everything is not ==
        self.assertFalse(self.jpg_obj == self.small_obj, 'Files are different')
        self.assertTrue(self.jpg_obj != self.small_obj, 'Test != operator')

    def test_image_compare5(self):
        image_time = datetime.now()
        obj1 = ImageCleaner(copy_file(self.jpg_obj.path, self.run_base, new_name='new_name.jpg'))
        obj2 = ImageCleaner(copy_file(self.jpg_obj.path, self.input_folder))

        # test5 -> less than and greater than
        set_date(obj1.path, image_time - timedelta(days=1))
        set_date(obj2.path, image_time)

        self.assertTrue(obj1 > obj2, "Older time stamps are >")  # ack
        self.assertTrue(obj2 < obj1, "Newer time stamps are <")  # ack

    def test_image_compare6(self):
        image_time = datetime.now()
        no_date = ImageCleaner(copy_file(self.jpg_obj.path, self.run_base, new_name='new_name.jpg'))
        with_date = ImageCleaner(copy_file(self.jpg_obj.path, self.input_folder))

        # test6 -> Null date values
        set_date(no_date.path, None)
        set_date(with_date.path, image_time)

        self.assertTrue(no_date < with_date)
        self.assertFalse(no_date > with_date)

        self.assertTrue(with_date > no_date)
        self.assertFalse(with_date < no_date)

    def test_image_compare7(self):
        # test last - two different objects
        fake_file = FileCleaner(self.jpg_obj.path)
        self.assertFalse(self.jpg_obj == fake_file)
        self.assertFalse(self.jpg_obj > fake_file)
        self.assertFalse(self.jpg_obj < fake_file)

    def test_small(self):
        self.assertFalse(self.jpg_obj.is_small)
        self.assertTrue(self.small_obj.is_small)

    def test_registrations_1(self):
        # Test 1 -> simple registration and de-registration
        self.jpg_obj.clear_caches()
        self.assertListEqual(self.jpg_obj.get_registered(), [], 'Get all reg.  should have 0 elements')

        self.assertEqual(output_files, {}, 'Nothing registered')
        self.assertFalse(self.jpg_obj.is_registered())
        self.jpg_obj.register()
        self.assertEqual(self.jpg_obj.get_registered()[0], self.jpg_obj, 'Get all reg.  should have 1 elements')

    def test_registrations_2(self):
        self.jpg_obj.clear_caches()
        self.jpg_obj.register()

        self.jpg_obj.de_register()
        self.assertEqual(len(output_files), 0, 'Nothing registered')
        self.assertFalse(self.jpg_obj.is_registered())

        # test2 multiple copies
    def test_registrations_3(self):

        new_dir = self.input_folder.joinpath('other_dir')
        os.mkdir(new_dir)

        new_file = copy_file(self.jpg_obj.path, new_dir)
        new_obj = ImageCleaner(new_file)

        self.jpg_obj.register()
        new_obj.register()
        self.assertEqual(len(output_files), 1, 'Hash should only have one element')

        self.assertTrue(self.jpg_obj.is_registered())
        self.assertTrue(new_obj.is_registered())

    def test_registrations_4(self):
        self.jpg_obj.register()
        new_dir = self.input_folder.joinpath('other_dir')
        os.mkdir(new_dir)

        # This should be a different size
        new_obj = ImageCleaner(create_image_file(new_dir.joinpath(self.jpg_obj.path.name), None, text='X'))
        new_obj.register()

        # test3  - De-register one of the copies
        new_obj.de_register()
        self.assertEqual(len(output_files), 1, 'Hash should only have one element')
        self.assertEqual(len(output_files[new_obj.registry_key]), 1, 'One elements (same key')

        # test4 - Lookup with various path options
        self.assertTrue(new_obj.is_registered(), 'Test True by name')
        self.assertFalse(new_obj.is_registered(by_path=True), 'Test Fail with path')

    def test_relocate_to_nowhere(self):
        self.jpg_obj.relocate_file(None)
        self.assertTrue(self.jpg_obj.path.exists(), 'Relocate to None does nothing')
        self.assertFalse(self.jpg_obj.is_registered(), 'Must be specifically registered')

        self.jpg_obj.relocate_file(None, register=True)
        self.assertFalse(self.jpg_obj.is_registered(), 'Nice try,  can not register something that does not exist')
        self.assertTrue(self.jpg_obj.path.exists(), 'We sill exists')

        self.jpg_obj.relocate_file(None, register=True, remove=True)
        self.assertTrue(self.jpg_obj.path.exists(), 'A lot of work for a unlink')
        self.assertFalse(self.jpg_obj.is_registered(), 'Do to None - got nothing to register')

    def test_relocate_with_registration_and_remove(self):

        self.assertTrue(self.jpg_obj.path.exists(), 'File Exists')
        self.assertFalse(self.jpg_obj.is_registered(), 'Is not registered')
        self.assertFalse(self.output_folder.joinpath(self.jpg_obj.path.name).exists(), 'Nothing on the output')

        self.jpg_obj.relocate_file(self.output_folder)  # Default is don't register,  don't remove
        self.assertTrue(self.jpg_obj.path.exists(), 'Test no erase')
        self.assertTrue(self.output_folder.joinpath(self.jpg_obj.path.name).exists(), 'Relocate worked')
        self.assertFalse(self.jpg_obj.is_registered(), 'Registration did not happen')

    def test_relocate_with_registration_and_remove2(self):

        original_path = self.jpg_obj.path
        self.jpg_obj.relocate_file(self.output_folder, register=True,  remove=True)
        self.assertFalse(original_path.exists(), 'Test erase')
        self.assertEqual(self.output_folder.joinpath(self.jpg_obj.path.name), self.jpg_obj.path, 'Path updated')
        self.assertTrue(self.output_folder.joinpath(self.jpg_obj.path.name).exists(), 'Relocate worked')
        self.assertTrue(self.jpg_obj.is_registered(), 'Registration happen')

    def test_rollover(self):
        """
        create a file,  and roll it over
        :return:
        """
        image_file = ImageCleaner(create_image_file(self.input_folder, None))
        basic_name = f'{image_file.path.stem}*{image_file.path.suffix}'
        self.assertEqual(count_files(self.output_folder, basic_name), 0, 'Does not exist')
        for count in range(21):
            copy_file(image_file.path, self.output_folder)
            image_file.rollover_file(self.output_folder.joinpath(image_file.path.name))
            self.assertEqual(count_files(self.output_folder, basic_name), count + 1, 'Keep rolling over')
        self.assertEqual(count_files(self.output_folder, basic_name), 21, 'We should be full')
        copy_file(image_file.path, self.output_folder)
        image_file.rollover_file(self.output_folder.joinpath(image_file.path.name))
        self.assertEqual(count_files(self.output_folder, basic_name), 21, 'Still 21')

    def test_rollover_does_not_exist(self):
        """
        Try to roll over a file that does not exist,   quietly does nothing
        Add the file,   try it again, and it should work
        Try again, and it should still be 1

        :return:
        """
        image_file = ImageCleaner(create_image_file(self.input_folder, None))
        basic_name = f'{image_file.path.stem}*{image_file.path.suffix}'
        self.assertEqual(count_files(self.output_folder, basic_name), 0, 'Does not exist')
        image_file.rollover_file(self.output_folder.joinpath(image_file.path.name))
        self.assertEqual(count_files(self.output_folder, basic_name), 0, "Can't Rollover nothing")
        copy_file(image_file.path, self.output_folder)
        image_file.rollover_file(self.output_folder.joinpath(image_file.path.name))
        self.assertEqual(count_files(self.output_folder, basic_name), 1, 'Ok,  that worked')
        image_file.rollover_file(self.output_folder.joinpath(image_file.path.name))
        self.assertEqual(count_files(self.output_folder, basic_name), 1, 'Ok,  that worked')

    def test_relocate_with_rollover(self):
        """
        Input.
        ./jpeg_image.jpg
        ./small_image.jpg
        ./Input/jpeg_image.jpg  - new_obj (which is the same as small_image)

        Test 1 - Relocate jpeg_image - ensure copy is the same
        Test 2 - Relocate again - no rollover (only one output)
        Test 3 - Relocate again - with rollover (two copies same contents)
        Test 4 - Relocate Input - no rollover - Nothing is done.
        Test 5 - Relocate Input again,  with rollover  (image and _0 are both small),  _1 is large
        :return:
        """
        basic_name = f'{self.jpg_obj.path.stem}*{self.jpg_obj.path.suffix}'
        new_obj = ImageCleaner(copy_file(self.small_obj.path, self.input_folder, new_name=self.jpg_obj.path.name))
        orig_path = self.jpg_obj.path
        new_path = new_obj.path
        copied_name = self.output_folder.joinpath(self.jpg_obj.path.name)
        rollover_name1 = self.output_folder.joinpath(f'{self.jpg_obj.path.stem}_0{self.jpg_obj.path.suffix}')
        rollover_name2 = self.output_folder.joinpath(f'{self.jpg_obj.path.stem}_1{self.jpg_obj.path.suffix}')

        # Control test
        self.assertEqual(count_files(self.output_folder, basic_name), 0, 'No relocations')
        self.assertEqual(self.jpg_obj.path.name, new_obj.path.name, 'Same names')
        self.assertFalse(cmp(self.jpg_obj.path, new_obj.path), 'Different content')

        # Test 1
        self.jpg_obj.relocate_file(self.output_folder)
        self.assertEqual(count_files(self.output_folder, basic_name), 1, 'Moved once')
        self.assertTrue(copied_name.exists(), 'Copy Worked')
        self.assertTrue(cmp(copied_name, self.jpg_obj.path), 'Content same')

        # Test 2
        self.jpg_obj.path = orig_path
        self.jpg_obj.relocate_file(self.output_folder, rollover=False)
        self.assertEqual(count_files(self.output_folder, basic_name), 1, 'Moved Twice')
        self.assertTrue(copied_name.exists(), 'Copy Worked')
        self.assertTrue(cmp(copied_name, self.jpg_obj.path), 'File is the same')

        # Test 3
        self.jpg_obj.path = orig_path
        self.jpg_obj.relocate_file(self.output_folder, rollover=True)
        self.assertEqual(count_files(self.output_folder, basic_name), 2, 'Rolled Over')
        self.assertTrue(copied_name.exists(), 'Copy Worked')
        self.assertTrue(rollover_name1.exists(), 'Rollover Worked')
        self.assertTrue(cmp(copied_name, self.jpg_obj.path), 'File is the same')
        self.assertTrue(cmp(copied_name, rollover_name1), 'File is the same')

        # Test 4
        new_obj.relocate_file(self.output_folder, rollover=False)
        self.assertEqual(count_files(self.output_folder, basic_name), 2, 'Rolled Over')
        self.assertTrue(copied_name.exists(), 'Copy Worked')
        self.assertTrue(rollover_name1.exists(), 'Rollover still there')
        self.assertTrue(cmp(copied_name, orig_path), 'File is the same')
        self.assertTrue(cmp(orig_path, rollover_name1), 'File is the same')

        # Test 4b
        new_obj.relocate_file(self.output_folder, rollover=False, remove=True)
        self.assertEqual(count_files(self.output_folder, basic_name), 2, 'Rolled Over')
        self.assertTrue(new_path.exists(), 'remove Failed')
        self.assertTrue(copied_name.exists(), 'Copy Worked')
        self.assertTrue(rollover_name1.exists(), 'Rollover still there')
        self.assertTrue(cmp(copied_name, orig_path), 'File is the same')
        self.assertTrue(cmp(orig_path, rollover_name1), 'File is the same')

        # Test 5
        new_obj.path = new_path
        new_obj.relocate_file(self.output_folder, rollover=True, remove=True)
        self.assertEqual(count_files(self.output_folder, basic_name), 3, 'Moved Twice')
        self.assertFalse(new_path.exists(), 'remove Failed')
        self.assertTrue(copied_name.exists(), 'Copy Worked')
        self.assertTrue(rollover_name1.exists(), 'Rollover Worked')
        self.assertTrue(rollover_name2.exists(), 'Rollover Worked')

        self.assertTrue(cmp(copied_name, new_obj.path), 'File is the same')
        self.assertTrue(cmp(rollover_name1, orig_path), 'File is the same')
        self.assertTrue(cmp(rollover_name2, orig_path), 'Rolled over original')

    def test_relocate_with_permission_errors(self):

        if platform.system() not in ['Windows', 'win32']:  # pragma: no cover
            # chmod does not work in windows
            new_dir = Path(self.temp_base.name).joinpath('ReadOnly')
            os.makedirs(new_dir)
            new_obj = ImageCleaner(create_image_file(new_dir.joinpath('err_image.jpg'), None))
            os.chmod(new_dir, 0o500)  # Owner +r+x

            with self.assertLogs('Cleaner', level='DEBUG') as logs:
                error_value = f'DEBUG:Cleaner:{new_obj.path} could not be removed'
                new_obj.relocate_file(self.output_folder, remove=True)
                self.assertTrue(logs.output[len(logs.output) - 2].startswith(error_value))

            with self.assertLogs('Cleaner', level='ERROR') as logs:
                self.jpg_obj.relocate_file(new_dir)
                error_value = f'ERROR:Cleaner:Can not write to {new_dir}'
                self.assertTrue(logs.output[len(logs.output) - 2].startswith(error_value), 'R/O remove')

    @patch('piexif.load')
    def test_invalid_date(self,  my_exif_dict):
        my_exif_dict.return_value = {}
        self.assertIsNone(self.jpg_obj.date)
        my_exif_dict.return_value = {'0th': {piexif.ImageIFD.DateTime: b'1961:09:27 00:00:00'}}
        self.assertEqual(self.jpg_obj.date, DATE_SPEC)
        self.jpg_obj._date = None  # pylint: disable=protected-access
        my_exif_dict.return_value = {'Exif': {piexif.ExifIFD.DateTimeDigitized: b'1961:09:26 00:00:00'}}
        self.assertEqual(self.jpg_obj.date, DATE_SPEC-timedelta(days=1))
        self.jpg_obj._date = None  # pylint: disable=protected-access
        my_exif_dict.return_value = {'Exif': {piexif.ExifIFD.DateTimeOriginal: b'1961:09:25 00:00:00'}}
        self.assertEqual(self.jpg_obj.date, DATE_SPEC-timedelta(days=2))


    def test_convert_non_heic(self):
        self.assertEqual(self.jpg_obj, self.jpg_obj.convert(self.run_base, None))

    def test_convert_defaults(self):
        if platform.system() not in ['win32', 'Windows']:  # pragma: no cover

            with self.assertLogs('Cleaner', level='DEBUG') as logs:
                new_obj = self.heic_obj.convert(self.run_base, self.migration_base.joinpath('heic'))  # Default  remove=True
                self.assertTrue(logs.output[len(logs.output) - 1].startswith('DEBUG:Cleaner:Will not copy to myself'))

            self.assertNotEqual(self.heic_obj, new_obj)
            self.assertEqual(self.heic_obj.path.stem, new_obj.path.stem)
            self.assertEqual(new_obj.path.suffix, '.jpg')
            self.assertTrue(new_obj.path.exists())
            self.assertTrue(self.heic_obj.path.exists())

    def test_convert_no_migrate_inplace(self):
        if platform.system() not in ['win32', 'Windows']:  # pragma: no cover

            new_obj = self.heic_obj.convert(self.run_base, None, remove=True)  # Default  remove=True

            self.assertNotEqual(self.heic_obj, new_obj)
            self.assertEqual(self.heic_obj.path.stem, new_obj.path.stem)
            self.assertEqual(new_obj.path.suffix, '.jpg')
            self.assertTrue(new_obj.path.exists())
            self.assertFalse(self.heic_obj.path.exists())

    def test_convert_exists(self):
        if platform.system() not in ['win32', 'Windows']:  # pragma: no cover
            new_obj = self.heic_obj.convert(self.run_base, None, remove=False)
            self.assertTrue(new_obj.path.exists())
            self.assertTrue(self.heic_obj.path.exists())
            with self.assertLogs('Cleaner', level='DEBUG') as logs:
                self.heic_obj.convert(self.run_base, None, remove=False)
                error_value = f'DEBUG:Cleaner:Cleaning up {new_obj.path} - It already exists'
                self.assertEqual(logs.output[len(logs.output) - 1], error_value, 'Output Exists')

    def test_convert_not_in_place(self):
        new_obj = self.heic_obj.convert(self.run_base, self.migration_base, remove=False)
        self.assertTrue(new_obj.path.exists())
        self.assertTrue(self.heic_obj.path.exists())

    def test_convert_not_in_place_no_migration(self):
        new_obj = self.heic_obj.convert(self.run_base, None, remove=False)
        self.assertTrue(new_obj.path.exists())
        self.assertTrue(self.heic_obj.path.exists())

    @patch('platform.system')
    def test_run_on_windows(self, mock_system):
        mock_system.return_value = 'Windows'
        with self.assertLogs('Cleaner', level='ERROR') as logs:
            new = self.heic_obj.convert(self.run_base, None, remove=False)
            error_value = 'ERROR:Cleaner:Conversion from HEIC is not supported on Windows'
            self.assertTrue(logs.output[len(logs.output) - 1].startswith(error_value), 'windows HEIC')
            self.assertEqual(new, self.heic_obj)

    def test_non_image_open(self):
        file1 = ImageCleaner(create_file(self.input_folder.joinpath('a.jpg'), ))
        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            file1.open_image()
            error_value = f'DEBUG:Cleaner:open_image UnidentifiedImageError {file1.path}'
            self.assertTrue(logs.output[len(logs.output) - 1].startswith(error_value), 'non-image')


class FileTests(Cleaners):
    """
    some data is dependent on folders, so we will test > < and date functions with folders
    """

    def test_compare(self):
        file1 = FileCleaner(create_file(self.input_folder.joinpath('a.file'), data='File Contents1'))
        file2 = FileCleaner(create_file(self.input_folder.joinpath('b.file'), data='File Contents2'))
        file3 = FileCleaner(create_file(self.input_folder.joinpath('c.file'), data='File Contents1'))

        self.assertFalse(file1 == file2)
        self.assertTrue(file1 == file3)
        self.assertTrue(file1 != file2)
        self.assertFalse(file1 != file3)

        self.assertFalse(file1.is_small)

    def test_dates(self):
        # pylint: disable=protected-access
        cur_time = datetime.now().replace(microsecond=0)
        old_time = cur_time - timedelta(days=2)
        older_time = old_time.timestamp()
        newer = FileCleaner(create_file(self.input_folder.joinpath('a1.file'), data='File Contents1'))
        older = FileCleaner(create_file(self.input_folder.joinpath('b1.file'), data='File Contents1'))
        different = FileCleaner(create_file(self.input_folder.joinpath('c1.file'), data='File Contents2'))
        os.utime(older.path, times=(older_time, older_time))

        self.assertEqual(newer, older)
        self.assertNotEqual(newer, different)
        self.assertEqual(older.date, old_time)
        self.assertTrue(newer > older)
        self.assertTrue(older < newer)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
