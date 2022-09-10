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

from Backend.Cleaner import ImageCleaner, file_cleaner

sys.path.append(f'{Path.home().joinpath("ImageClean")}')  # I got to figure out this hack, venv doesn't work real well
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))


class PhotoTests(unittest.TestCase):

    my_location = Path(os.path.dirname(__file__))
    small_file = my_location.joinpath('data').joinpath('small_image.jpg')
    heic_file = my_location.joinpath('data').joinpath('heic_image.HEIC')
    jpg_file = my_location.joinpath('data').joinpath('jpeg_image.jpg')

    def setUp(self):
        super(PhotoTests, self).setUp()
        self.temp_input = tempfile.TemporaryDirectory()
        self.temp_output = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_input.cleanup()
        self.temp_output.cleanup()
        super(PhotoTests, self).tearDown()

    @staticmethod
    def copy_file(in_file: Path, out_path: Path) -> Path:
        if not out_path.exists():
            os.makedirs(out_path)
        new = out_path.joinpath(in_file.name)
        copyfile(str(in_file), new)
        return new

    def copy_to_input(self, physical_file: Path) -> Path:
        """
        Given a physical file,  move the file to the input directory
        physical_file:  The file to process
        :return: Path to new file
        """
        return self.copy_file(physical_file, Path(self.temp_input.name))

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



if __name__ == '__main__':  # pragma: no cover
    unittest.main()
