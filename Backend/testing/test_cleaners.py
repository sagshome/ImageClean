"""
Test cases in this file process actual images,  I was going to MOCK everything but in the end I opted to exercise the
imaging frameworks.   There files are used,  a standard jpg,  a thumbnail and a HEIC file

"""
import os
import piexif
import sys
import tempfile

import unittest

from datetime import datetime, timedelta
from pathlib import Path
from shutil import copyfile
from unittest import TestCase
from unittest.mock import patch

from Backend.Cleaner import ImageCleaner, Cleaner, FolderCleaner, FileCleaner, \
    file_cleaner, duplicate_hash, root_path_list

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

        # Make basic folders
        self.temp_base = tempfile.TemporaryDirectory()
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
    def copy_file(in_file: Path, out_path: Path, cleanup: bool = False, new_name: str = None) -> Path:

        new_name = in_file.name if not new_name else new_name
        new = out_path.joinpath(new_name)
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


class ImageCleanerTests(Cleaners):

    def setUp(self):
        """
        No need to tearDown since super will clean up input directory
        :return:
        """
        super(ImageCleanerTests, self).setUp()

        self.small_obj = ImageCleaner(
            self.copy_to_input(self.my_location.joinpath('data').joinpath('small_image.jpg')), None)
        self.heic_obj = ImageCleaner(
            self.copy_to_input(self.my_location.joinpath('data').joinpath('heic_image.HEIC')), None)
        self.jpg_obj = ImageCleaner(
            self.copy_to_input(self.my_location.joinpath('data').joinpath('jpeg_image.jpg')), None)

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

    def test_date_no_date(self):

        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            date_value = self.jpg_obj.get_date_from_image()
            self.assertEqual(logs.output[0], f'DEBUG:Cleaner:Could not find a date in {self.jpg_obj.path}')
            self.assertIsNone(date_value, 'Image time should be None')

    def test_date_date(self):
        image_time = datetime.now() - timedelta(days=1)
        self.set_date(self.jpg_obj.path, image_time)
        new_time = self.jpg_obj.get_date_from_image()
        self.assertEqual(new_time.year, image_time.year, 'Matching year')
        self.assertEqual(new_time.month, image_time.month, 'Matching month')
        self.assertEqual(new_time.day, image_time.day, 'Matching day')
        # don't care about anything else

        invalid_image = ImageCleaner(self.create_file(self.input_folder.joinpath('invalid.jpg')))
        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            _ = invalid_image.get_date_from_image()
            self.assertEqual(logs.output[0], f'DEBUG:Cleaner:Failed to load {invalid_image.path} - Invalid JPEG/TIFF')

        os.unlink(invalid_image.path)
        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            _ = invalid_image.get_date_from_image()
            self.assertEqual(logs.output[0], f'DEBUG:Cleaner:Failed to load {invalid_image.path} - File not Found')

    def test_image_data(self):
        self.assertListEqual(self.jpg_obj._image_data, [], "Image data should be empty")
        _ = self.jpg_obj.image_data
        self.assertNotEqual(self.jpg_obj._image_data, [], "Image data has been cached")

    def test_image_compare(self):
        """
        Test ==, !=, < and >
        """

        # test1 -> Same File - Different paths
        copy_obj = ImageCleaner(self.copy_file(self.jpg_obj.path, self.run_base), None)
        self.assertTrue(copy_obj == self.jpg_obj, 'Files are the same/name and size')

    def test_image_compare2(self):
        # test2 -> Same File,  Different names
        clone_obj = ImageCleaner(
            self.copy_file(self.jpg_obj.path, self.jpg_obj.path.parent, new_name='new_name.jpg'), None)  # make a copy
        self.assertTrue(self.jpg_obj == clone_obj, 'Files are still the same')

    def test_image_compare3(self):
        # test3 -> Add a timestamp,   should still be ==
        clone_obj = ImageCleaner(
            self.copy_file(self.jpg_obj.path, self.jpg_obj.path.parent, new_name='new_name.jpg'), None)  # make a copy

        image_time = datetime.now()
        self.set_date(clone_obj.path, image_time)
        self.assertTrue(self.jpg_obj == clone_obj, 'Files are still the same, regardless of dates')

    def test_image_compare4(self):

        # test4 -> make sure everything is not ==
        self.assertFalse(self.jpg_obj == self.small_obj, 'Files are different')
        self.assertTrue(self.jpg_obj != self.small_obj), 'Test != operator'

    def test_image_compare5(self):
        image_time = datetime.now()
        obj1 = ImageCleaner(self.copy_file(self.jpg_obj.path, self.run_base, new_name='new_name.jpg'), None)
        obj2 = ImageCleaner(self.copy_file(self.jpg_obj.path, self.run_base), None)

        # test5 -> less than and greater than
        self.set_date(obj1.path, image_time - timedelta(days=1))
        self.set_date(obj2.path, image_time)

        self.assertTrue(obj1 > obj2, "Older time stamps are >")  # ack
        self.assertTrue(obj2 < obj1, "Newer time stamps are <")  # ack

    def test_image_compare6(self):
        image_time = datetime.now()
        no_date = ImageCleaner(self.copy_file(self.jpg_obj.path, self.run_base, new_name='new_name.jpg'), None)
        with_date = ImageCleaner(self.copy_file(self.jpg_obj.path, self.run_base), None)

        # test6 -> Null date values
        self.set_date(no_date.path, None)
        self.set_date(with_date.path, image_time)

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

    # def test_update_date(self):
    #    image_time = datetime.now()
    #    no_date = ImageCleaner(self.copy_file(self.jpg_obj.path, self.run_base, new_name='new_name.jpg'), None)
    #    self.set_date(no_date.path, None)
    #    self.assertIsNone(no_date.date)

    #    date_in_name = ImageCleaner(self.copy_file(
    #        self.jpg_obj.path, self.run_base, new_name=image_time.strftime("%Y%m%d-%H%M%S") + no_date.path.suffix),
    #        None)
    #    self.set_date(date_in_name.path, None)
    #    self.assertIsNotNone(date_in_name.date)

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

        new_file = self.copy_file(self.jpg_obj.path, new_dir)
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
        new_file = self.copy_file(self.jpg_obj.path, self.run_base)
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
        self.assertEqual(new_obj.get_new_path(self.output_folder, invalid_parents=['Directory2', ]), output,
                         'Desc path test')

        output = self.output_folder.joinpath('Directory2')
        self.assertEqual(new_obj.get_new_path(self.output_folder, invalid_parents=['Directory1', ]), output,
                         'Desc path test')

        # test7
        new_file = self.copy_file(new_file, self.root_folder.path, cleanup=True)
        new_obj = ImageCleaner(new_file, self.root_folder)
        output = self.output_folder
        self.assertEqual(new_obj.get_new_path(self.output_folder, invalid_parents=[]), output, 'Desc no date/desc test')

    def test_relocate_1(self):

        self.jpg_obj.relocate_file(None)

        self.jpg_obj.relocate_file(self.output_folder, register=True)
        self.assertTrue(self.jpg_obj.path.exists(), 'Test no erase')
        self.assertTrue(self.output_folder.joinpath(self.jpg_obj.path.name).exists, 'Copy worked')
        self.assertTrue(self.jpg_obj.is_registered, 'Registration worked')
        self.jpg_obj.de_register()
        os.unlink(self.output_folder.joinpath(self.jpg_obj.path))

    def test_relocate_2(self):

        self.jpg_obj.relocate_file(self.output_folder, remove=True)
        self.assertFalse(self.jpg_obj.path.exists(), 'Test erase')
        self.assertTrue(self.output_folder.joinpath(self.jpg_obj.path.name).exists, 'Copy worked')
        self.copy_to_input(self.output_folder.joinpath(self.jpg_obj.path.name))

        self.jpg_obj.relocate_file(self.output_folder, rollover=False)

        self.assertFalse(self.output_folder.joinpath(f'{self.jpg_obj.path.name}_0').exists(), 'Rollover test')
        self.jpg_obj.relocate_file(self.output_folder)
        self.assertTrue(self.jpg_obj.path.exists(), 'Rollover worked')

        self.jpg_obj.relocate_file(self.output_folder)
        self.assertTrue(self.jpg_obj.path.exists(), 'Rollover worked again')

        new_dir = self.output_folder.joinpath('NewDirectory')
        self.jpg_obj.relocate_file(new_dir)
        self.assertTrue(new_dir.joinpath(self.jpg_obj.path.name), 'Directory was created')

        os.chmod(new_dir, 0o500)  # Owner +r+x
        new_image = ImageCleaner(new_dir.joinpath(self.jpg_obj.path.name), None)
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
        #image = ImageCleaner(Path('/a/b/20221225_235959z.jpg'), None)
        #self.assertIsNone(image.get_date_from_path_name(), 'Image name has no date values')

        image = ImageCleaner(Path('/a/b/20221225-235959.jpg'), None)
        self.assertEqual(image.get_date_from_path_name(), test_date, 'Discovered date1')
        image = ImageCleaner(Path('/a/b/a20221225-235959.jpg'), None)
        self.assertIsNone(image.get_date_from_path_name(), 'Image name has no date values')
        #image = ImageCleaner(Path('/a/b/20221225-235959z.jpg'), None)
        #self.assertIsNone(image.get_date_from_path_name(), 'Image name has no date values')

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
        new_obj = self.heic_obj.convert(self.run_base, self.migration_base)  # Default  remove=True

        self.assertNotEqual(self.heic_obj, new_obj)
        self.assertEqual(self.heic_obj.path.stem, new_obj.path.stem)
        self.assertEqual(new_obj.path.suffix, '.jpg')
        self.assertTrue(new_obj.path.exists())
        self.assertFalse(self.heic_obj.path.exists())

    def test_convert_no_migrate_inplace(self):
        new_obj = self.heic_obj.convert(self.run_base, None, remove=True)  # Default  remove=True

        self.assertNotEqual(self.heic_obj, new_obj)
        self.assertEqual(self.heic_obj.path.stem, new_obj.path.stem)
        self.assertEqual(new_obj.path.suffix, '.jpg')
        self.assertTrue(new_obj.path.exists())
        self.assertFalse(self.heic_obj.path.exists())

    def test_convert_exists(self):
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
            error_value = f'ERROR:Cleaner:Conversion from HEIC is not supported on Windows'
            self.assertTrue(logs.output[len(logs.output)-1].startswith(error_value), 'windows HEIC')
            self.assertEqual(new, self.heic_obj)

    def test_non_image_open(self):
        file1 = ImageCleaner(self.create_file(self.input_folder.joinpath('a.jpg'), data='File Contents1'), None)
        with self.assertLogs('Cleaner', level='DEBUG') as logs:
            file1.open_image()
            error_value = f'DEBUG:Cleaner:open_image UnidentifiedImageError {file1.path}'
            self.assertTrue(logs.output[len(logs.output)-1].startswith(error_value), 'non-image')


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
        self.assertFalse(file1.is_small)

    def test_dates(self):
        cur_time = datetime.now().replace(microsecond=0)
        old_time = cur_time - timedelta(days=2)
        older_time = old_time.timestamp()
        newer = FileCleaner(self.create_file(self.input_folder.joinpath('a1.file'), data='File Contents1'), None)
        older = FileCleaner(self.create_file(self.input_folder.joinpath('b1.file'), data='File Contents1'), None)
        different = FileCleaner(self.create_file(self.input_folder.joinpath('c1.file'), data='File Contents2'), None)
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
        super(FolderTests, self).setUp()
        self.custom_dir1 = FolderCleaner(self.input_folder.joinpath('custom1'))
        self.custom_dir2 = FolderCleaner(self.input_folder.joinpath('custom2'))
        self.date_dir1 = FolderCleaner(self.input_folder.joinpath('2022').joinpath('12').joinpath('24'))
        self.date_dir2 = FolderCleaner(self.input_folder.joinpath('2022').joinpath('12').joinpath('25'))
        self.no_date = FolderCleaner(self.input_folder)

        os.makedirs(self.custom_dir1.path, exist_ok=False)
        os.makedirs(self.custom_dir2.path, exist_ok=False)
        os.makedirs(self.date_dir1.path, exist_ok=False)
        os.makedirs(self.date_dir2.path, exist_ok=False)

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


    def test_folder_date(self):
        self.assertIsNone(self.custom_dir1.date)
        self.assertEqual(self.date_dir1.date, datetime(2022, 12, 24))
        child = FolderCleaner(self.date_dir1.path.joinpath('Custom3'), parent=self.date_dir1)
        child2 = FolderCleaner(child.path.joinpath('Custom4'), parent=child)
        child3 = FolderCleaner(child2.path.joinpath('Custom5'), parent=child2)
        self.assertEqual(self.date_dir1.date, child3.date)

    def test_size(self):
        input_obj = FolderCleaner(self.input_folder, None)
        self.assertEqual(input_obj.size, 3, 'Initial Folder size test')

        self.assertTrue(input_obj.is_small, 'Less then 10 is  small')
        for x in range(6):
            self.create_file(f"junk_{x}", empty=True)
        self.assertTrue(input_obj.is_small, 'Less then 10 is  small')
        self.create_file('one_little_mint', empty=True)
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
            ["2003_04_06_TriptoFalls", None],  # todo: this will fail 22 chars not spaces.  Should fix it!
            ["12-Aug-2014", None]
        ]

        for folder, description in tests:
            child = FolderCleaner(self.custom_dir1.path.joinpath(folder), parent=self.custom_dir1)
            if description:
                self.assertEqual(child.description, description)
            else:
                self.assertIsNone(child.description, f'Processing - {folder} with {description}')

        base = FolderCleaner(self.custom_dir1.path.joinpath('funky_app_something'), parent=None, app_name='funky_app')
        self.assertIsNone(base.description)

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


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
