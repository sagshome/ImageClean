"""
Test cases in this file process actual images,  I was going to MOCK everything but in the end I opted to exercise the
imaging frameworks.   There files are used,  a standard jpg,  a thumbnail and a HEIC file

"""
import os
import piexif
import stat
import sys
import tempfile

import unittest

from datetime import datetime, timedelta
from pathlib import Path
from shutil import copyfile
from unittest import TestCase
from unittest.mock import patch, Mock, MagicMock

from Backend.Cleaner import ImageCleaner, Cleaner, file_cleaner, FolderCleaner, FileCleaner

sys.path.append(f'{Path.home().joinpath("ImageClean")}')  # I got to figure out this hack, venv doesn't work real well
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


class CleanersInitTest(TestCase):
    """
    Test out the basic init avoided class Cleaners for setup
    """

    def test_null_values(self):
        new_obj = Cleaner(Path('/fake_parent/fake_dir/fake.file'), None)
        self.assertEqual(new_obj.path, Path('/fake_parent/fake_dir/fake.file'))
        self.assertIsNone(new_obj.folder)
        self.assertIsNone(new_obj._date)

        size_of_movies = len(new_obj.all_movies)
        again = Cleaner(Path('/c/b.a'), None)
        self.assertEqual(size_of_movies, len(again.all_movies))

        _ = new_obj.all_movies.pop()
        other = Cleaner(Path('/a/b.c'), None)
        self.assertNotEqual(size_of_movies, len(other.all_movies))


class Cleaners(TestCase):

    def setUp(self):
        super(Cleaners, self).setUp()
        # define standard files
        self.my_location = Path(os.path.dirname(__file__))
        self.small_file = self.my_location.joinpath('data').joinpath('small_image.jpg')
        self.heic_file = self.my_location.joinpath('data').joinpath('heic_image.HEIC')
        self.jpg_file = self.my_location.joinpath('data').joinpath('jpeg_image.jpg')

        # Make basic folders
        self.temp_base = tempfile.TemporaryDirectory()
        self.output_folder = Path(self.temp_base.name).joinpath('Output')
        self.input_folder = Path(self.temp_base.name).joinpath('Input')
        os.mkdir(self.output_folder)
        os.mkdir(self.input_folder)

        self.root_folder = FolderCleaner(self.input_folder,
                                         root_folder=self.input_folder,
                                         output_folder=self.output_folder)
        self.root_folder.description = None

    def tearDown(self):
        self.temp_base.cleanup()
        super(Cleaners, self).tearDown()

    def create_file(self, name: str, data: str = None, empty: bool = False) -> Path:
        name = self.input_folder.joinpath(name)
        f = open(name, 'w+')
        if not empty:
            if not data:
                f.write(str(name))
            else:
                f.write(data)
        f.close()
        return name

    @staticmethod
    def copy_file(in_file: Path, out_path: Path, cleanup: bool = False) -> Path:
        if not out_path.exists():
            os.makedirs(out_path)
        new = out_path.joinpath(in_file.name)
        copyfile(str(in_file), new)
        if cleanup:
            os.unlink(in_file)
        return new

    def copy_to_input(self, physical_file: Path) -> Path:
        """
        Given a physical file,  move the file to the input directory
        physical_file:  The file to process
        :return: Path to new file
        """
        return self.copy_file(physical_file, self.input_folder)


class CleanerTests(Cleaners):

    def create_file(self, name: str, empty: bool = False) -> Path:
        name = self.input_folder.joinpath(name)
        f = open(name, 'w+')
        if not empty:
            f.write(str(name))
        f.close()
        return name

    def setUp(self):
        super(CleanerTests, self).setUp()
        self.file1 = Cleaner(self.create_file('a.file'), None)
        self.file2 = Cleaner(self.create_file('b.file'), None)

    def test_compare(self):
        with self.assertRaises(NotImplementedError):
            _ = self.file1 == self.file2
        with self.assertRaises(NotImplementedError):
            _ = self.file1 > self.file2
        with self.assertRaises(NotImplementedError):
            _ = self.file1 < self.file2
        with self.assertRaises(NotImplementedError):
            _ = self.file1 != self.file2

    def test_cleanup(self):
        """
        self.test_input is initialized with two files a.file, and b.file  to test this autocleanup we need to make
        image and movie files and write them to a directory and ensure they disappear, but not the other files

        :return:
        """
        new1 = self.create_file(f'foo{self.file1.all_movies[0]}')
        new2 = self.create_file(f'bar{self.file1.all_images[0]}')
        self.copy_file(new2, self.input_folder.joinpath('test_cleanup_dir'), cleanup=True)

        total_files = 0
        for root, dirs, files in os.walk(self.input_folder):
            total_files += len(files)
        self.assertEqual(total_files, 4, "Should have 4 files at the start")
        new_obj = Cleaner(new1, None)
        new_obj.clean_working_dir(self.input_folder)
        total_files = 0
        for root, dirs, files in os.walk(self.input_folder):
            total_files += len(files)
        self.assertEqual(total_files, 2, "Should have 2 files at the end")

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
        empty_file = self.create_file('fake', empty=True)
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


class PhotoTests(Cleaners):

    @staticmethod
    def set_date(original_file: Path, new_date: datetime):
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
        pass

    def test_date(self):
        image_time = datetime.now() - timedelta(days=1)
        original_obj = ImageCleaner(self.jpg_file, None)
        self.assertIsNone(original_obj.get_date_from_image(), 'Image time should be None')
        new = self.copy_to_input(self.jpg_file)
        self.set_date(new, image_time)
        new_obj = ImageCleaner(new, None)
        new_time = new_obj.get_date_from_image()
        self.assertEqual(new_time.year, image_time.year, 'Matching year')
        self.assertEqual(new_time.month, image_time.month, 'Matching month')
        self.assertEqual(new_time.day, image_time.day, 'Matching day')
        # don't care about anything else

    def test_image_data(self):
        original_obj = ImageCleaner(self.jpg_file, None)
        self.assertListEqual(original_obj._image_data, [], "Image data should be empty")
        data = original_obj.image_data
        self.assertNotEqual(original_obj._image_data, [], "Image data has been cached")

    def test_image_compare(self):
        """
        Test ==, !=, < and >
        """

        # test1 -> Same File - Different paths
        copy_file = self.copy_to_input(self.jpg_file)
        orig_obj = ImageCleaner(self.jpg_file, None)
        copy_obj = ImageCleaner(copy_file, None)
        self.assertTrue(copy_obj == orig_obj, 'Files are the same/name and size')

        # test2 -> Same File,  Different names
        clone_file = copy_file.parent.joinpath('new_name.jpg')  # Make a copy
        copyfile(copy_file, clone_file)
        clone_obj = ImageCleaner(clone_file, None)
        self.assertTrue(copy_obj == clone_obj, 'Files are still the same')

        # test3 -> Add a timestamp,   should still be ==
        image_time = datetime.now()
        self.set_date(copy_file, image_time)
        copy_obj = ImageCleaner(copy_file, None)
        self.assertTrue(copy_obj == clone_obj, 'Files are still the same')

        # test4 -> make sure everything is not ==
        diff_obj = ImageCleaner(self.small_file, None)
        self.assertFalse(copy_obj == diff_obj, 'Files are different')
        self.assertTrue(copy_obj != diff_obj), 'Test != operator'

        # test5 -> less than and greater than
        self.set_date(clone_file, image_time - timedelta(days=1))
        clone_obj = ImageCleaner(clone_file, None)

        self.assertTrue(clone_obj > copy_obj, "Older time stamps are >")
        self.assertTrue(copy_obj < clone_obj, "Newer time stamps are <")

    def test_registrations(self):

        # Test 1 -> simple registration and de-registration
        image = ImageCleaner(self.jpg_file, None)
        self.assertEqual(0, len(image.get_all_registered()), 'Get all reg.  should have 0 elements')

        self.assertEqual(len(image.duplicate_hash), 0, 'Nothing registered')
        self.assertFalse(image.is_registered())
        image.register()
        self.assertEqual(1, len(image.get_all_registered()), 'Get all reg.  should have 1 elements')

        with self.assertLogs('Cleaner', level='ERROR') as logs:
            image.register()
            self.assertTrue(logs.output[0].startswith('ERROR:Cleaner:Trying to re_register'), 'Failed to log error')

        self.assertTrue(image.is_registered())
        self.assertEqual(len(image.duplicate_hash), 1, 'Something registered')
        image.de_register()
        self.assertEqual(len(image.duplicate_hash), 0, 'Nothing registered')
        self.assertFalse(image.is_registered())

        # test2 multiple copies
        new_dir = self.input_folder.joinpath('other_dir')
        os.mkdir(new_dir)

        new_file = self.copy_file(self.jpg_file, new_dir)
        new_obj = ImageCleaner(new_file, None)

        image.register()
        new_obj.register()
        self.assertEqual(len(new_obj.duplicate_hash), 1, 'Hash should only have one element')
        self.assertEqual(len(new_obj.duplicate_hash[new_obj.registry_key]), 2, 'Two elements (same key')
        self.assertEqual(new_obj.duplicate_hash, image.duplicate_hash, 'Shared hash test')

        self.assertTrue(image.is_registered())
        self.assertTrue(new_obj.is_registered())

        self.assertEqual(2, len(new_obj.get_all_registered()), 'Get all reg.  should have 2 elements')

        # test3  - De-register one of the copies
        new_obj.de_register()
        self.assertEqual(len(new_obj.duplicate_hash), 1, 'Hash should only have one element')
        self.assertEqual(len(new_obj.duplicate_hash[new_obj.registry_key]), 1, 'One elements (same key')

        # test4 - Lookup with various path options
        self.assertTrue(new_obj.is_registered(), 'Test True by name')
        self.assertFalse(new_obj.is_registered(by_path=True), 'Test Fail with path')
        self.assertTrue(new_obj.is_registered(by_path=True, alternate_path=image.path.parent),
                        'Test Pass with alternate path')

        with self.assertLogs('Cleaner', level='ERROR') as logs:
            new_obj.de_register()
            self.assertTrue(logs.output[0].startswith('ERROR:Cleaner:Trying to remove non-'), 'Failed to log error')

    def test_get_new_path(self):
        """
        This is a great deal of the logic with cleaners
        :return:
        """
        image_time = datetime.now() - timedelta(days=1)
        new_directory1 = FolderCleaner(self.output_folder.joinpath('Directory1'), parent=self.root_folder)
        new_directory2 = FolderCleaner(new_directory1.path.joinpath('Directory2'), parent=new_directory1)
        os.mkdir(new_directory1.path)
        os.mkdir(new_directory2.path)
        new_file = self.copy_file(self.jpg_file, self.root_folder.path)
        self.set_date(new_file, image_time)
        new_obj = ImageCleaner(new_file, self.root_folder)

        # test1
        self.assertIsNone(new_obj.get_new_path(None), "Without a base,  we have no path")

        # test2
        output = self.output_folder.\
            joinpath(str(image_time.year)).\
            joinpath(str(image_time.month)).\
            joinpath(str(image_time.day))
        self.assertEqual(new_obj.get_new_path(self.output_folder, invalid_parents=[]), output, 'Date Based path test')

        # test3
        new_file = self.copy_file(new_file, new_directory1.path, cleanup=True)
        new_obj = ImageCleaner(new_file, new_directory1)
        output = self.output_folder.joinpath(str(image_time.year)).joinpath('Directory1')
        self.assertEqual(new_obj.get_new_path(self.output_folder, invalid_parents=[]), output, 'Desc path test')

        # test4
        new_file = self.copy_file(new_file, new_directory2.path, cleanup=True)
        new_obj = ImageCleaner(new_file, new_directory2)
        output = self.output_folder.joinpath(str(image_time.year)).joinpath('Directory1').joinpath('Directory2')
        self.assertEqual(new_obj.get_new_path(self.output_folder, invalid_parents=[]), output, 'Desc path test')

        # test5
        self.set_date(new_file, None)
        new_obj = ImageCleaner(new_file, new_directory2)
        output = self.output_folder.joinpath('Directory1').joinpath('Directory2')
        self.assertEqual(new_obj.get_new_path(self.output_folder, invalid_parents=[]), output, 'Desc path test')

        # test6
        output = self.output_folder.joinpath('Directory1')
        self.assertEqual(new_obj.get_new_path(self.output_folder, invalid_parents=['Directory2',]), output,
                         'Desc path test')

        output = self.output_folder.joinpath('Directory2')
        self.assertEqual(new_obj.get_new_path(self.output_folder, invalid_parents=['Directory1',]), output,
                         'Desc path test')

        # test7
        new_file = self.copy_file(new_file, self.root_folder.path, cleanup=True)
        new_obj = ImageCleaner(new_file, self.root_folder)
        output = self.output_folder
        self.assertEqual(new_obj.get_new_path(self.output_folder, invalid_parents=[]), output, 'Desc no date/desc test')

    def test_relocate_1(self):
        new = self.copy_to_input(self.jpg_file)
        image = ImageCleaner(new, None)

        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            image.relocate_file(None)
            self.assertTrue(logs.output[0].startswith('DEBUG:Cleaner:Attempted to relocate to NONE'), 'null test')

        image.relocate_file(self.output_folder, register=True)
        self.assertTrue(new.exists(), 'Test no erase')
        self.assertTrue(self.output_folder.joinpath(new.name).exists, 'Copy worked')
        self.assertTrue(image.is_registered, 'Registration worked')
        image.de_register()
        os.unlink(self.output_folder.joinpath(new.name))

        image = ImageCleaner(new, None)
        image.relocate_file(self.output_folder, remove=True)
        self.assertFalse(new.exists(), 'Test erase')
        self.assertTrue(self.output_folder.joinpath(new.name).exists, 'Copy worked')
        self.copy_to_input(self.output_folder.joinpath(new.name))

        with self.assertLogs('Cleaner', level='ERROR') as logs:
            image.relocate_file(self.output_folder, rollover=False)
            self.assertTrue(logs.output[0].startswith('ERROR:Cleaner:Will not overwrite'), 'Will not overwrite')

        self.assertFalse(self.output_folder.joinpath(f'{new.name}_0').exists(), 'Rollover test')
        image.relocate_file(self.output_folder)
        new_file = self.output_folder.joinpath(f'{new.stem}_0.{new.suffix}')
        self.assertTrue(new.exists(), 'Rollover worked')

        image.relocate_file(self.output_folder)
        new_file = self.output_folder.joinpath(f'{new.stem}_1.{new.suffix}')
        self.assertTrue(new.exists(), 'Rollover worked again')

        new_dir = self.output_folder.joinpath('NewDirectory')
        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            image.relocate_file(new_dir, create_dir=False)
            self.assertTrue(logs.output[0].startswith('DEBUG:Cleaner:Create Dir is'), 'Do not create output path')

        image.relocate_file(new_dir, create_dir=True)
        self.assertTrue(new_dir.joinpath(new.name), 'Directory was created')

        os.chmod(new_dir, 0o500)  # Owner +r+x
        new_image = ImageCleaner(new_dir.joinpath(new.name), None)
        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            new_image.relocate_file(self.output_folder, rollover=True, remove=True)
            error_value = f'DEBUG:Cleaner:{new_image.path}'
            self.assertTrue(logs.output[len(logs.output)-1].startswith(error_value), 'R/O remove')

    def test_get_data_from_path_name(self):

        image = ImageCleaner(Path('/a/b/c.jpg'), None)
        self.assertIsNone(image.get_date_from_path_name(), 'Image name has no date values')

        test_date = datetime(year=2022, month=12, day=25, hour=23, minute=59, second=59)
        image = ImageCleaner(Path('/a/b/20221225_235959.jpg'), None)
        self.assertEqual(image.get_date_from_path_name(), test_date, 'Discovered date1')
        image = ImageCleaner(Path('/a/b/a20221225_235959.jpg'), None)
        self.assertIsNone(image.get_date_from_path_name(), 'Image name has no date values')
        image = ImageCleaner(Path('/a/b/20221225_235959z.jpg'), None)
        self.assertIsNone(image.get_date_from_path_name(), 'Image name has no date values')

        image = ImageCleaner(Path('/a/b/20221225-235959.jpg'), None)
        self.assertEqual(image.get_date_from_path_name(), test_date, 'Discovered date1')
        image = ImageCleaner(Path('/a/b/a20221225-235959.jpg'), None)
        self.assertIsNone(image.get_date_from_path_name(), 'Image name has no date values')
        image = ImageCleaner(Path('/a/b/20221225-235959z.jpg'), None)
        self.assertIsNone(image.get_date_from_path_name(), 'Image name has no date values')

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


class FileTests(Cleaners):
    """
    some of the data is dependent on folders so we will test > < and date functions with folders
    """

    def test_compare(self):
        file1 = FileCleaner(self.create_file(self.input_folder.joinpath('a.file'), data='File Contents1'), None)
        file2 = FileCleaner(self.create_file(self.input_folder.joinpath('b.file'), data='File Contents2'), None)
        file3 = FileCleaner(self.create_file(self.input_folder.joinpath('c.file'), data='File Contents1'), None)

        self.assertFalse(file1 == file2)
        self.assertTrue(file1 == file3)
        self.assertTrue(file1 != file2)
        self.assertFalse(file1 != file3)

        self.assertFalse(file1.is_small)
        file4 = FileCleaner(self.create_file(self.input_folder.joinpath('d.file'), empty=True), None)
        self.assertFalse(file1.is_small)


class FolderTests(Cleaners):
    """
    """

    def test_caches(self):
        new = FolderCleaner(Path('/a/b/c.d'))
        self.assertEqual(new.root_folders, [])

        new2 = FolderCleaner(Path('/b/a/c.d'), root_folder=Path('/c/d/a.b'), output_folder=Path('/d/c/b.a'))
        self.assertEqual(len(new2.root_folders), 2)
        self.assertEqual(len(new.root_folders), 2)




if __name__ == '__main__':  # pragma: no cover
    unittest.main()
