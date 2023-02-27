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

# pylint: disable=import-error
from backend.cleaner import ImageCleaner, Cleaner, FolderCleaner, FileCleaner, \
    file_cleaner, duplicate_hash, root_path_list, PICTURE_FILES, MOVIE_FILES
from Utilities.test_utilities import copy_file, create_file, create_image_file, set_date, count_files, \
    DATE_SPEC, DIR_SPEC


class CleanerUtilsTest(unittest.TestCase):
    def setUp(self):
        super().setUp()
        Cleaner.clear_caches()

    def test_objects(self):
        for image_type in PICTURE_FILES:
            my_object = file_cleaner(Path(f'/fake/foo{image_type}'), None)
            self.assertEqual('ImageCleaner', my_object.__class__.__name__,
                             f'Expected ImageCleaner Object - got {my_object.__class__.__name__}')

        for image_type in MOVIE_FILES:
            my_object = file_cleaner(Path(f'/fake/foo{image_type}'), None)
            self.assertEqual('ImageCleaner', my_object.__class__.__name__,
                             f'{my_object.path} Expected ImageCleaner Object - got {my_object.__class__.__name__}')

        my_object = file_cleaner(Path('/fake/foo.text'), None)
        self.assertEqual('FileCleaner', my_object.__class__.__name__,
                         f'{my_object.path} Expected FileCleaner Object - got {my_object.__class__.__name__}')

        my_object = file_cleaner(Path.home(), None)
        self.assertEqual('FolderCleaner', my_object.__class__.__name__,
                         f'{my_object.path} Expected FolderCleaner Object - got {my_object.__class__.__name__}')


class CleanersInitTest(TestCase):
    """
    Test out the basic init avoided class Cleaners for setup
    """

    def setUp(self):
        super().setUp()
        Cleaner.clear_caches()

    def test_null_values(self):
        # pylint: disable=protected-access
        new_obj = Cleaner(Path('/fake_parent/fake_dir/fake.file'), None)
        self.assertEqual(new_obj.path, Path('/fake_parent/fake_dir/fake.file'))
        self.assertIsNone(new_obj.folder)
        self.assertIsNone(new_obj._date)

    def test_caching(self):
        # pylint: disable=protected-access
        new_path = Path('/somepath/foo')
        new_path2 = Path('/somepath/bar')
        self.assertEqual(len(Cleaner._get_root_path()), 0, 'Root Path is Empty')
        Cleaner.add_to_root_path(new_path)
        Cleaner.add_to_root_path(new_path2)
        self.assertEqual(len(Cleaner._get_root_path()), 2, 'Root Path contains two paths')
        Cleaner.add_to_root_path(new_path)
        self.assertEqual(len(Cleaner._get_root_path()), 2, 'Root Path still contains two paths')
        Cleaner.reset()
        self.assertEqual(len(Cleaner._get_root_path()), 0, 'Root Path is Empty')


class Cleaners(TestCase):

    def setUp(self):
        super().setUp()
        # define standard files
        self.my_location = Path(os.path.dirname(__file__))

        # Make basic folders
        self.temp_base = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.output_folder = Path(self.temp_base.name).joinpath('Output')
        self.input_folder = Path(self.temp_base.name).joinpath('Input')
        os.mkdir(self.output_folder)
        os.mkdir(self.input_folder)

        Cleaner.clear_caches()
        self.root_folder = FolderCleaner(self.input_folder,
                                         root_folder=self.input_folder,
                                         output_folder=self.output_folder)
        self.root_folder.description = None

        self.migration_base = Path(self.temp_base.name)
        self.run_base = self.migration_base

    def tearDown(self):
        self.temp_base.cleanup()
        super().tearDown()


class CleanerTests(Cleaners):

    def setUp(self):
        super().setUp()
        self.file1 = Cleaner(create_file(self.input_folder.joinpath('a.file')), None)
        self.file2 = Cleaner(create_file(self.input_folder.joinpath('b.file')), None)

    def test_compare(self):
        with self.assertRaises(NotImplementedError):
            _ = self.file1 == self.file2
        with self.assertRaises(NotImplementedError):
            _ = self.file1 > self.file2
        with self.assertRaises(NotImplementedError):
            _ = self.file1 < self.file2
        with self.assertRaises(NotImplementedError):
            _ = self.file1 != self.file2

    def test_no_convert(self):
        self.assertEqual(self.file1.convert(None, None).path, self.file1.path)

    def test_notimplemented(self):
        with self.assertRaises(NotImplementedError):
            _ = self.file1.date
        with self.assertRaises(NotImplementedError):
            _ = self.file1.is_small

    def test_is_valid(self):
        self.assertTrue(self.file1.is_valid, 'Valid file is not valid')
        fake = Cleaner(Path('/a/b.c'), None)
        self.assertFalse(fake.is_valid, 'Testing a fake file')
        empty_file = create_file(self.input_folder.joinpath('fake'), empty=True)
        empty = Cleaner(Path(empty_file), None)
        self.assertFalse(empty.is_valid, 'Testing an empty file')
        folder = Cleaner(self.input_folder, None)
        self.assertFalse(folder.is_valid, 'Testing a directory like it a file')

    def test_registry_key(self):
        original_path = self.file1.path
        expected_key = self.file1.path.stem.upper()
        self.assertEqual(expected_key, self.file1.registry_key)

        self.file1.path = Path('something_else')
        self.assertEqual(expected_key, self.file1.registry_key, 'Since it is cached.')

        self.file1 = Cleaner(original_path.parent.joinpath(f'{original_path.stem}_1{original_path.suffix}'), None)
        self.assertEqual(expected_key, self.file1.registry_key)

        self.file1 = Cleaner(original_path.joinpath(f'{original_path.stem}_99{original_path.suffix}'), None)
        self.assertEqual(expected_key, self.file1.registry_key)

        self.file1 = Cleaner(original_path.parent.joinpath(f'{original_path.stem}_100{original_path.suffix}'), None)
        self.assertNotEqual(expected_key, self.file1.registry_key)

        self.file1 = Cleaner(original_path.parent.joinpath(f'{original_path.stem}1{original_path.suffix}'), None)
        self.assertNotEqual(expected_key, self.file1.registry_key)

        self.file1 = Cleaner(original_path.parent.joinpath(f'{original_path.stem}-1{original_path.suffix}'), None)
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
            create_image_file(Path(self.temp_base.name).joinpath('small_image.jpg'), None, small=True), None)

        self.heic_obj = ImageCleaner(
            copy_file(self.my_location.joinpath('data').joinpath('heic_image.HEIC'), Path(self.temp_base.name)), None)

        self.jpg_obj = ImageCleaner(
            create_image_file(Path(self.temp_base.name).joinpath('jpeg_image.jpg'), None), None)

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
        image_error = ImageCleaner(Path('fake_faker_fakest.jpg'), None)
        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            image_error.open_image()
            self.assertTrue(logs.output[0].startswith('DEBUG:Cleaner:open_image OSError'),  image_error.path.name)

    def test_os_image_error_not_found(self):
        image_error = ImageCleaner(Path('fake_faker_fakest.jpg'), None)
        with self.assertLogs('Cleaner', level='ERROR') as logs:
            result = image_error == image_error  # pylint: disable=comparison-with-itself
            self.assertTrue(logs.output[0].startswith(f'ERROR:Cleaner:File {image_error.path.name}'),  "Doesn't exist.")
        self.assertFalse(result, 'Compare to non-existent file should fail')

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
        copy_obj = ImageCleaner(copy_file(self.jpg_obj.path, self.input_folder), None)
        self.assertTrue(copy_obj == self.jpg_obj, 'Files are the same/name and size')

    def test_image_compare2(self):
        # test2 -> Same File,  Different names
        clone_obj = ImageCleaner(
            copy_file(self.jpg_obj.path, self.jpg_obj.path.parent, new_name='new_name.jpg'), None)  # make a copy
        self.assertTrue(self.jpg_obj == clone_obj, 'Files are still the same')

    def test_image_compare3(self):
        # test3 -> Add a timestamp,   should still be ==
        clone_obj = ImageCleaner(
            copy_file(self.jpg_obj.path, self.jpg_obj.path.parent, new_name='new_name.jpg'), None)  # make a copy

        image_time = datetime.now()
        set_date(clone_obj.path, image_time)
        self.assertTrue(self.jpg_obj == clone_obj, 'Files are still the same, regardless of dates')

    def test_image_compare4(self):
        # test4 -> make sure everything is not ==
        self.assertFalse(self.jpg_obj == self.small_obj, 'Files are different')
        self.assertTrue(self.jpg_obj != self.small_obj, 'Test != operator')

    def test_image_compare5(self):
        image_time = datetime.now()
        obj1 = ImageCleaner(copy_file(self.jpg_obj.path, self.run_base, new_name='new_name.jpg'), None)
        obj2 = ImageCleaner(copy_file(self.jpg_obj.path, self.input_folder), None)

        # test5 -> less than and greater than
        set_date(obj1.path, image_time - timedelta(days=1))
        set_date(obj2.path, image_time)

        self.assertTrue(obj1 > obj2, "Older time stamps are >")  # ack
        self.assertTrue(obj2 < obj1, "Newer time stamps are <")  # ack

    def test_image_compare6(self):
        image_time = datetime.now()
        no_date = ImageCleaner(copy_file(self.jpg_obj.path, self.run_base, new_name='new_name.jpg'), None)
        with_date = ImageCleaner(copy_file(self.jpg_obj.path, self.input_folder), None)

        # test6 -> Null date values
        set_date(no_date.path, None)
        set_date(with_date.path, image_time)

        self.assertTrue(no_date < with_date)
        self.assertFalse(no_date > with_date)

        self.assertTrue(with_date > no_date)
        self.assertFalse(with_date < no_date)

    def test_image_compare7(self):
        # test last - two different objects
        fake_file = FileCleaner(self.jpg_obj.path, None)
        self.assertFalse(self.jpg_obj == fake_file)
        self.assertFalse(self.jpg_obj > fake_file)
        self.assertFalse(self.jpg_obj < fake_file)

    def test_small(self):
        self.assertFalse(self.jpg_obj.is_small)
        self.assertTrue(self.small_obj.is_small)

    def test_registrations(self):
        # Test 1 -> simple registration and de-registration
        self.jpg_obj.clear_caches()

        self.assertEqual(0, len(self.jpg_obj.get_all_registered()), 'Get all reg.  should have 0 elements')

        self.assertEqual(duplicate_hash, {}, 'Nothing registered')
        self.assertFalse(self.jpg_obj.is_registered())
        self.jpg_obj.register()
        self.assertEqual(1, len(self.jpg_obj.get_all_registered()), 'Get all reg.  should have 1 elements')

        with self.assertLogs('Cleaner', level='ERROR') as logs:
            self.jpg_obj.register()
            self.assertTrue(logs.output[0].startswith('ERROR:Cleaner:Trying to re_register'), 'Failed to log error')

        self.assertTrue(self.jpg_obj.is_registered())
        self.assertEqual(len(duplicate_hash), 1, 'Something registered')
        self.jpg_obj.de_register()
        self.assertEqual(len(duplicate_hash), 0, 'Nothing registered')
        self.assertFalse(self.jpg_obj.is_registered())

        # test2 multiple copies
        new_dir = self.input_folder.joinpath('other_dir')
        os.mkdir(new_dir)

        new_file = copy_file(self.jpg_obj.path, new_dir)
        new_obj = ImageCleaner(new_file, None)

        self.jpg_obj.register()
        new_obj.register()
        self.assertEqual(len(duplicate_hash), 1, 'Hash should only have one element')
        self.assertEqual(len(duplicate_hash[new_obj.registry_key]), 2, 'Two elements (same key')

        self.assertTrue(self.jpg_obj.is_registered())
        self.assertTrue(new_obj.is_registered())

        self.assertEqual(2, len(new_obj.get_all_registered()), 'Get all reg.  should have 2 elements')

        # test3  - De-register one of the copies
        new_obj.de_register()
        self.assertEqual(len(duplicate_hash), 1, 'Hash should only have one element')
        self.assertEqual(len(duplicate_hash[new_obj.registry_key]), 1, 'One elements (same key')

        # test4 - Lookup with various path options
        self.assertTrue(new_obj.is_registered(), 'Test True by name')
        self.assertFalse(new_obj.is_registered(by_path=True), 'Test Fail with path')
        self.assertTrue(new_obj.is_registered(by_path=True, alternate_path=self.jpg_obj.path.parent),
                        'Test Pass with alternate path')

        with self.assertLogs('Cleaner', level='ERROR') as logs:
            new_obj.de_register()
            self.assertTrue(logs.output[0].startswith('ERROR:Cleaner:Trying to remove non-'), 'Failed to log error')

    def test_relocate_to_nowhere(self):
        self.jpg_obj.relocate_file(None)
        self.assertTrue(self.jpg_obj.path.exists(), 'Relocate to None does nothing')
        self.assertFalse(self.jpg_obj.is_registered(), 'Must be specifically registered')

        self.jpg_obj.relocate_file(None, register=True)
        self.assertFalse(self.jpg_obj.is_registered(), 'Nice try,  can not register something that does not exist')
        self.assertTrue(self.jpg_obj.path.exists(), 'We sill exists')

        self.jpg_obj.relocate_file(None, register=True, remove=True)
        self.assertFalse(self.jpg_obj.path.exists(), 'A lot of work for a unlink')
        self.assertFalse(self.jpg_obj.is_registered(), 'Do to None - got nothing to register')

    def test_relocate_with_registration_and_remove(self):

        self.assertTrue(self.jpg_obj.path.exists(), 'File Exists')
        self.assertFalse(self.jpg_obj.is_registered(), 'Is not registered')
        self.assertFalse(self.output_folder.joinpath(self.jpg_obj.path.name).exists(), 'Nothing on the output')

        self.jpg_obj.relocate_file(self.output_folder)  # Default is don't register,  don't remove
        self.assertTrue(self.jpg_obj.path.exists(), 'Test no erase')
        self.assertTrue(self.output_folder.joinpath(self.jpg_obj.path.name).exists(), 'Relocate worked')
        self.assertFalse(self.jpg_obj.is_registered(), 'Registration did not happen')

        os.unlink(self.output_folder.joinpath(self.jpg_obj.path.name))
        original_path = self.jpg_obj.path
        self.jpg_obj.relocate_file(self.output_folder, register=True,  remove=True)  # Default is don't register,  don't remove
        self.assertFalse(original_path.exists(), 'Test erase')
        self.assertEqual(self.output_folder.joinpath(self.jpg_obj.path.name), self.jpg_obj.path, 'Path updated')
        self.assertTrue(self.output_folder.joinpath(self.jpg_obj.path.name).exists(), 'Relocate worked')
        self.assertTrue(self.jpg_obj.is_registered(), 'Registration happen')

    def test_relocate_with_rollover(self):
        basic_name = f'{self.jpg_obj.path.stem}*{self.jpg_obj.path.suffix}'
        new_obj = ImageCleaner(copy_file(self.small_obj.path, self.input_folder, new_name=self.jpg_obj.path.name), None)

        self.assertEqual(count_files(self.output_folder, basic_name), 0, 'No relocations')
        self.assertEqual(self.jpg_obj.path.name, new_obj.path.name, 'Two files - same name')
        self.assertFalse(cmp(self.jpg_obj.path, new_obj.path), 'File Not the same')

        self.jpg_obj.relocate_file(self.output_folder)
        self.assertEqual(count_files(self.output_folder, basic_name), 1, 'Moved once')
        self.assertTrue(self.output_folder.joinpath(self.jpg_obj.path.name).exists(), 'Copy Worked')
        self.assertTrue(cmp(self.output_folder.joinpath(self.jpg_obj.path.name), self.jpg_obj.path), 'File is the same')

        self.jpg_obj.relocate_file(self.output_folder, rollover=False)
        self.assertEqual(count_files(self.output_folder, basic_name), 1, 'Moved Twice')
        self.assertTrue(self.output_folder.joinpath(self.jpg_obj.path.name).exists(), 'Copy Worked')
        self.assertTrue(cmp(self.output_folder.joinpath(self.jpg_obj.path.name), self.jpg_obj.path), 'File is the same')

        new_obj.relocate_file(self.output_folder, rollover=True)
        self.assertEqual(count_files(self.output_folder, basic_name), 2, 'Moved Twice')
        self.assertTrue(self.output_folder.joinpath(self.jpg_obj.path.name).exists(), 'Copy Worked')
        self.assertTrue(self.output_folder.joinpath(f'{self.jpg_obj.path.stem}_0{self.jpg_obj.path.suffix}').exists(),
                        'Rollover Worked')
        self.assertTrue(cmp(self.output_folder.joinpath(self.jpg_obj.path.name), new_obj.path), 'File is the same')
        self.assertTrue(cmp(self.output_folder.joinpath(f'{self.jpg_obj.path.stem}_0{self.jpg_obj.path.suffix}'),
                            self.jpg_obj.path), 'File is the same')

    def test_relocate_with_permission_errors(self):

        if platform.system() not in ['Windows', 'win32']:  # pragma: no cover
            # chmod does not work in windows
            new_dir = Path(self.temp_base.name).joinpath('ReadOnly')
            os.makedirs(new_dir)
            new_obj = ImageCleaner(create_image_file(new_dir.joinpath('err_image.jpg'), None), None)
            os.chmod(new_dir, 0o500)  # Owner +r+x

            with self.assertLogs('Cleaner', level='DEBUG') as logs:
                error_value = f'DEBUG:Cleaner:{new_obj.path} could not be removed'
                new_obj.relocate_file(self.output_folder, remove=True)
                self.assertTrue(logs.output[len(logs.output) - 1].startswith(error_value))

            with self.assertLogs('Cleaner', level='ERROR') as logs:
                self.jpg_obj.relocate_file(new_dir)
                error_value = f'ERROR:Cleaner:Can not write to {new_dir}'
                self.assertTrue(logs.output[len(logs.output) - 1].startswith(error_value), 'R/O remove')

    def test_get_data_from_path_name(self):
        image = ImageCleaner(Path('/a/b/c.jpg'), None)
        self.assertIsNone(image.get_date_from_path_name(), 'Image name has no date values')

        test_date = datetime(year=2022, month=12, day=25)
        image = ImageCleaner(Path('/a/b/20221225_235959.jpg'), None)
        self.assertEqual(image.get_date_from_path_name(), test_date, 'Discovered date1')
        image = ImageCleaner(Path('/a/b/a20221225_235959.jpg'), None)
        self.assertIsNone(image.get_date_from_path_name(), 'Image name has no date values')
        # image = ImageCleaner(Path('/a/b/20221225_235959z.jpg'), None)
        # self.assertIsNone(image.get_date_from_path_name(), 'Image name has no date values')

        image = ImageCleaner(Path('/a/b/20221225-235959.jpg'), None)
        self.assertEqual(image.get_date_from_path_name(), test_date, 'Discovered date1')
        image = ImageCleaner(Path('/a/b/a20221225-235959.jpg'), None)
        self.assertIsNone(image.get_date_from_path_name(), 'Image name has no date values')
        # image = ImageCleaner(Path('/a/b/20221225-235959z.jpg'), None)
        # self.assertIsNone(image.get_date_from_path_name(), 'Image name has no date values')

        test_date = datetime(year=2022, month=12, day=25)
        image = ImageCleaner(Path('/a/b/2022:12:25.jpg'), None)
        self.assertEqual(image.get_date_from_path_name(), test_date, 'Discovered date1')
        image = ImageCleaner(Path('/a/b/x2022:12:25.jpg'), None)
        self.assertIsNone(image.get_date_from_path_name(), 'Image name has no date values')
        image = ImageCleaner(Path('/a/b/2022:12:25x.jpg'), None)
        self.assertEqual(image.get_date_from_path_name(), test_date, 'Discovered date1')

        image = ImageCleaner(Path('/a/b/25-Dec-2022.jpg'), None)
        self.assertEqual(image.get_date_from_path_name(), test_date, 'Discovered date1')
        image = ImageCleaner(Path('/a/b/x25-Dec-2022.jpg'), None)
        self.assertIsNone(image.get_date_from_path_name(), 'Image name has no date values')
        image = ImageCleaner(Path('/a/b/25-Dec-2022 Foobar.jpg'), None)
        self.assertEqual(image.get_date_from_path_name(), test_date, 'Discovered date1')

        test_date = datetime(year=2022, month=12, day=1)

        image = ImageCleaner(Path('/a/b/2022-12.jpg'), None)
        self.assertIsNone(image.get_date_from_path_name(), 'Image name has no date values')
        image = ImageCleaner(Path('/a/b/2022-12-Foobar.jpg'), None)
        self.assertEqual(image.get_date_from_path_name(), test_date, 'Discovered date1')
        image = ImageCleaner(Path('/a/b/2022-12.jpg'), None)
        self.assertIsNone(image.get_date_from_path_name(), 'Image name has no date values')

    def test_get_data_from_folder_name(self):
        image = ImageCleaner(Path('/a/b/c.jpg'), None)
        self.assertIsNone(image.get_date_from_folder_names(), 'Image name has no date values')

        test_date = datetime(year=2022, month=12, day=25)
        image.path = Path('/a/2022-12-25/c.jpg')
        self.assertEqual(image.get_date_from_folder_names(), test_date, 'Discovered date1')
        image.path = Path('/a/2022/12/25/c.jpg')
        self.assertEqual(image.get_date_from_folder_names(), test_date, 'Discovered date1')
        image.path = Path('/a/2022/12/25/foo/c.jpg')
        self.assertIsNone(image.get_date_from_folder_names(), 'Discovered date1')
        image.path = Path('/a/2022/12/32/c.jpg')
        self.assertIsNone(image.get_date_from_folder_names(), 'Discovered date1')

        test_date = datetime(year=2022, month=12, day=1)
        image.path = Path('/a/2022/12/c.jpg')
        self.assertEqual(image.get_date_from_folder_names(), test_date, 'Discovered date1')
        image.path = Path('/a/2022-12/c.jpg')
        self.assertEqual(image.get_date_from_folder_names(), test_date, 'Discovered date1')
        image.path = Path('/a/2022-13/c.jpg')
        self.assertIsNone(image.get_date_from_folder_names(), 'Discovered date1')

        test_date = datetime(year=2022, month=1, day=1)
        image.path = Path('/a/2022/c.jpg')
        self.assertEqual(image.get_date_from_folder_names(), test_date, 'Discovered date1')
        image.path = Path('/a/2022-XMAS/c.jpg')
        self.assertEqual(image.get_date_from_folder_names(), test_date, 'Discovered date1')

    def test_convert_non_heic(self):
        self.assertEqual(self.jpg_obj, self.jpg_obj.convert(self.run_base, None))

    def test_convert_defaults(self):
        if platform.system() not in ['win32', 'Windows']:  # pragma: no cover

            with self.assertLogs('Cleaner', level='DEBUG') as logs:
                new_obj = self.heic_obj.convert(self.run_base, self.migration_base)  # Default  remove=True
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
        file1 = ImageCleaner(create_file(self.input_folder.joinpath('a.jpg'), ), None)
        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            file1.open_image()
            error_value = f'DEBUG:Cleaner:open_image UnidentifiedImageError {file1.path}'
            self.assertTrue(logs.output[len(logs.output) - 1].startswith(error_value), 'non-image')


class FileTests(Cleaners):
    """
    some data is dependent on folders, so we will test > < and date functions with folders
    """

    def test_compare(self):
        file1 = FileCleaner(create_file(self.input_folder.joinpath('a.file'), data='File Contents1'), None)
        file2 = FileCleaner(create_file(self.input_folder.joinpath('b.file'), data='File Contents2'), None)
        file3 = FileCleaner(create_file(self.input_folder.joinpath('c.file'), data='File Contents1'), None)

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
        newer = FileCleaner(create_file(self.input_folder.joinpath('a1.file'), data='File Contents1'), None)
        older = FileCleaner(create_file(self.input_folder.joinpath('b1.file'), data='File Contents1'), None)
        different = FileCleaner(create_file(self.input_folder.joinpath('c1.file'), data='File Contents2'), None)
        os.utime(older.path, times=(older_time, older_time))

        self.assertEqual(newer, older)
        self.assertNotEqual(newer, different)
        self.assertEqual(older.date, old_time)
        self.assertTrue(newer > older)
        self.assertTrue(older < newer)

        newer._date = None
        older._date = None
        date_dir1 = FolderCleaner(self.input_folder.joinpath('2022').joinpath('12').joinpath('24'))
        date_dir2 = FolderCleaner(self.input_folder.joinpath('2022').joinpath('12').joinpath('25'))

        newer.folder = date_dir1
        older.folder = date_dir2
        self.assertTrue(newer < older, 'Folder dates take precedence')
        self.assertTrue(older > newer, 'Folder dates take precedence')
        self.assertFalse(newer > different, 'Folder dates take precedence')
        self.assertFalse(older < different, 'Folder dates take precedence')


class FolderTests(Cleaners):

    def setUp(self):
        super().setUp()
        self.custom_dir1 = FolderCleaner(self.input_folder.joinpath('custom1'))
        self.custom_dir2 = FolderCleaner(self.input_folder.joinpath('custom2'))
        self.date_dir1 = FolderCleaner(self.input_folder.joinpath(DIR_SPEC))
        self.date_dir2 = FolderCleaner(self.input_folder.joinpath('2022').joinpath('12').joinpath('25'))
        self.no_date = FolderCleaner(self.input_folder)

        os.makedirs(self.custom_dir1.path, exist_ok=False)
        os.makedirs(self.custom_dir2.path, exist_ok=False)
        os.makedirs(self.date_dir1.path, exist_ok=False)
        os.makedirs(self.date_dir2.path, exist_ok=False)

        self.folder_data = [
            # folder path,  date value, description
            ['1961/9/27', DATE_SPEC, None],
            ['2014/1961/09/27', DATE_SPEC, None],
            ['1961_9_27_Roxy5', DATE_SPEC, 'Roxy5'],
            ["1961-09-27 Murphy's Point", DATE_SPEC, "Murphy's Point"],
            ['1961_9_Sara', datetime(1961, 9, 1), 'Sara'],
            ['1961 - Camping', datetime(1961, 1, 1), 'Camping'],
            ['2014/2014/06/30/19610927-063739/zCMlYzsaTqyElbmIFHvvLw', None, None],
            ['2014/2014/06/30/19610927-063736', DATE_SPEC, None],
            ['1961_09_27_TriptoFalls', None, None],  # fails,  22 chars and no spaces - bogus clause
            ['27-Sep-1961', DATE_SPEC, None],
        ]

    def test_operators(self):
        self.assertTrue(self.custom_dir1 == self.custom_dir2)
        self.assertTrue(self.date_dir1 == self.date_dir2)
        self.assertTrue(self.custom_dir1 != self.date_dir1)
        self.assertFalse(self.custom_dir1 == self.date_dir1)

        self.assertTrue(self.custom_dir1 > self.date_dir1)
        self.assertTrue(self.date_dir1 < self.custom_dir1)
        self.assertFalse(self.custom_dir1 < self.date_dir1)

        self.assertFalse(self.custom_dir1 > self.custom_dir2)
        self.assertFalse(self.custom_dir1 < self.custom_dir2)
        self.assertFalse(self.date_dir1 > self.date_dir2)
        self.assertFalse(self.date_dir1 < self.date_dir2)

        self.assertFalse(self.date_dir1 > self.custom_dir1)
        self.assertFalse(self.no_date > self.date_dir1)
        self.assertTrue(self.no_date < self.date_dir1)
        self.assertTrue(self.date_dir1 > self.no_date)
        self.assertFalse(self.date_dir1 < self.no_date)

    def test_folder_data(self):
        for path, date_spec, description in self.folder_data:
            file = create_file(self.input_folder.joinpath(path).joinpath('fake.file'))
            folder = FolderCleaner(file.parent)
            self.assertEqual(folder.date, date_spec, f'Testing folder date {date_spec} on {file}')
            self.assertEqual(folder.description, description, f'Testing folder description on {file}')

    def test_size(self):
        input_obj = FolderCleaner(self.input_folder, None)
        self.assertEqual(input_obj.size, 4, 'Initial Folder size test')

        self.assertTrue(input_obj.is_small, 'Less then 10 is  small')
        for junk_i in range(5):
            create_file(self.input_folder.joinpath(f"junk_{junk_i}.jpg"), None)
        self.assertTrue(input_obj.is_small, 'Less then 10 is  small')
        create_file(self.input_folder.joinpath('one_little_mint.jpg'), None)
        self.assertFalse(input_obj.is_small, 'Less then 10 is  small')
        self.assertEqual(input_obj.size, 10, 'Large folder test')

    def test_descriptions(self):
        """
        It could have been apple,  but something was making/moving photos to  directories that look like:
        ./2014/2014/06/30/20140630-063736/f0ZEGHL8T5O60zAH8FBQZA
        That (stem value) is not a valid description  here are other we support

        pictures/2004_04_17_Roxy5 -> Roxy5
        pictures/2016-09-25 Murphys Point
        pictures/2003_10_Sara
        pictures/2016 - Camping
        pictures/Alex's House
        - pictures/2014/2014/06/30/20140630-063739/zCMlYzsaTqyElbmIFHvvLw
        - pictures/2014/2014/06/30/20140630-063736
        pictures/2003_04_06_TriptoFalls
        - pictures/12-Aug-2014


        :return:
        """
        tests = [
            ["2004_04_17_Roxy5", "Roxy5"],
            ["2016-09-25 Murphys Point", "Murphys Point"],
            ["2003_10_Sara", "Sara"],
            ["2016 - Camping", "Camping"],
            ["Alex's House", "Alex's House"],
            ["2014/2014/06/30/20140630-063739/zCMlYzsaTqyElbmIFHvvLw", None],
            ["2014/2014/06/30/20140630-063736", None],
            ["2003_04_06_TriptoFalls", None],
            ["12-Aug-2014", None]
        ]

        for folder, description in tests:
            child = FolderCleaner(self.custom_dir1.path.joinpath(folder), parent=self.custom_dir1)
            if description:
                self.assertEqual(child.description, description)
                self.assertTrue(child.named_folder)
            else:
                self.assertIsNone(child.description, f'Processing - {folder} with {description}')
                self.assertFalse(child.named_folder)

        base = FolderCleaner(self.custom_dir1.path.joinpath('funky_app_something'), parent=None, app_name='funky_app')
        self.assertIsNone(base.description)

    def test_recursive_lookup(self):
        pass

    def test_reset(self):
        self.assertEqual(len(root_path_list), 2, 'Default input / output')
        FolderCleaner.reset()
        self.assertEqual(len(root_path_list), 0, 'Reset Successful')

    def test_add_root(self):

        self.assertEqual(len(root_path_list), 2, 'Default input / output')
        Cleaner.add_to_root_path(Path('/tmp/foo'))
        self.assertEqual(len(root_path_list), 3, '+ foo')
        Cleaner.add_to_root_path(Path('/tmp/foo'))
        self.assertEqual(len(root_path_list), 3, 'too much foo')


class ImageConversionTests(Cleaners):
    def setUp(self):
        super().setUp()
        self.filepath = self.input_folder.joinpath('a.heic')
        self.file = ImageCleaner(create_file(self.filepath, data='File Contents1'), None)

    def test_only_heic(self):
        fake_jpeg = ImageCleaner(create_file(self.input_folder.joinpath('a.jpeg')), None)
        new = fake_jpeg.convert(self.input_folder, migrated_base=None, remove=True)
        self.assertEqual(fake_jpeg, new, 'No changes on JPEG file')

    @patch('platform.system')
    def test_never_on_windows(self, platform_system):
        platform_system.return_value = 'Windows'
        with self.assertLogs('Cleaner', level='ERROR') as logs:
            new = self.file.convert(self.input_folder, migrated_base=None, remove=True)
            self.assertEqual(logs.output[0], 'ERROR:Cleaner:Conversion from HEIC is not supported on Windows')
        self.assertIn(self.filepath.suffix.upper(), self.file.CONVERSION_SUFFIX, 'Conversion Suffix is correct')
        self.assertEqual(self.file, new, 'No changes on Windows file')


class ImageProcessingTests(Cleaners):
    """
    monkeyPatch the heck out of image processing.

    Using this as piexif constants seem to mess around with mock

    piexif.ExifIFD.DateTimeOriginal -> 36867
    piexif.ExifIFD.DateTimeDigitized -> 36868
    piexif.ImageIFD.DateTime -> 306
    """
    def setUp(self):
        super().setUp()
        self.orig = 36867
        self.digitized = 36868
        self.image_ifd = 306
        self.filepath = self.input_folder.joinpath('a.file')
        self.file = ImageCleaner(create_file(self.filepath, data='File Contents1'), None)

        self.data = {
            'Exif': {
                self.orig: bytes(DATE_SPEC.strftime('%Y:%m:%d 00:00:00'), 'utf-8'),
                self.digitized:  bytes((DATE_SPEC+timedelta(days=1)).strftime('%Y:%m:%d 00:00:00'), 'utf-8')
            },
            '0th': {
                self.image_ifd: bytes((DATE_SPEC+timedelta(days=2)).strftime('%Y:%m:%d 00:00:00'), 'utf-8')
            }
        }

    @patch('piexif.load')
    def test_no_date(self, piexif):
        piexif.return_value = {}
        self.assertIsNone(self.file.get_date_from_image(), 'Image has no date')

    @patch('piexif.load')
    def test_orig_date(self, piexif):
        piexif.return_value = self.data
        self.assertEqual(DATE_SPEC, self.file.get_date_from_image())

    @patch('piexif.load')
    def test_orig_ifd_date(self, piexif):
        del self.data['Exif'][self.orig]
        del self.data['Exif'][self.digitized]
        piexif.return_value = self.data
        self.assertEqual(DATE_SPEC+timedelta(days=2), self.file.get_date_from_image())

    @patch('piexif.load')
    def test_orig_digitized_date(self, piexif):
        del self.data['Exif'][self.orig]
        piexif.return_value = self.data
        self.assertEqual(DATE_SPEC+timedelta(days=1), self.file.get_date_from_image())

    @patch('piexif.load')
    def test_no_date_data(self, piexif):
        self.data['Exif'][self.orig] = None
        piexif.return_value = self.data
        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            self.file.get_date_from_image()
            self.assertEqual(logs.output[0], f'DEBUG:Cleaner:Could not find a date in {self.filepath}')

    @patch('piexif.load')
    def test_bad_date_data(self, piexif):
        self.data['Exif'][self.orig] = bytes('foo bar', 'utf-8')
        piexif.return_value = self.data
        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            self.file.get_date_from_image()
            self.assertEqual(logs.output[0], f'DEBUG:Cleaner:Corrupt date data {self.filepath}')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
