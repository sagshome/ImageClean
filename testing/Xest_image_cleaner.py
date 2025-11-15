import os
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from cmdline import main


class ActualScenarioTest(unittest.TestCase):
    """
    Create real world scenario's for testing.   This is perhaps not unit tests but system tests

    These tests cover all the duplicate scenarios


    """
    # pylint: disable=too-many-public-methods, too-many-instance-attributes
    def tearDown(self):
        self.temp_base.cleanup()
        super().tearDown()

    def setUp(self):
        super().setUp()
        self.my_location = Path(os.path.dirname(__file__))
        self.app_name = 'test_instance'

        # Make basic folders
        self.temp_base = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.output_folder = Path(self.temp_base.name).joinpath('Output')
        self.input_folder = Path(self.temp_base.name).joinpath('Input')

        os.mkdir(self.output_folder)
        os.mkdir(self.input_folder)

        print(f'{str(self)} - {self.temp_base.name}')

    # @patch('backend.image_clean.ImageClean.run')
    @patch('builtins.print')
    @patch('pathlib.Path.home')
    def test_no_parameters(self, home, my_print):
        home.return_value = Path(self.temp_base.name)

        with self.assertRaises(SystemExit) as se:
            main([])
        self.assertEqual(se.exception.code, 2, 'No parameter test')
        my_print.assert_called()

    @patch('builtins.print')
    @patch('pathlib.Path.home')
    def test_help(self, home, my_print):
        home.return_value = Path(self.temp_base.name)

        with self.assertRaises(SystemExit) as se:
            main(["program_name", '-h', str(self.output_folder)])
        self.assertEqual(se.exception.code, 2, 'No parameter test')
        my_print.assert_called()

    @patch('pathlib.Path.home')
    def test_input(self, home):
        home.return_value = Path(self.temp_base.name)

        my_app = main(["program_name", str(self.input_folder)])
        self.assertEqual(my_app.input_folder, Path(self.input_folder))
        self.assertEqual(my_app.output_folder, Path(self.input_folder))

    @patch('pathlib.Path.home')
    def test_bad_input(self, home):
        home.return_value = Path(self.temp_base.name)
        with self.assertRaises(SystemExit) as se:
            main(["program_name", f"-i{str(self.input_folder.joinpath('foobar'))}", str(self.output_folder)])
        self.assertEqual(se.exception.code, 3, 'Invalid image path')

    @patch('pathlib.Path.home')
    def test_options(self, home):
        home.return_value = Path(self.temp_base.name)

        my_app = main(["program_name", f"-crsdvi{str(self.input_folder)}", str(self.output_folder)])
        self.assertEqual(my_app.input_folder, Path(self.input_folder))
        self.assertEqual(my_app.output_folder, Path(self.output_folder))
        self.assertTrue(my_app.convert)
        self.assertFalse(my_app.keep_original_files)
        self.assertTrue(my_app.check_for_small)
        self.assertTrue(my_app.verbose)
        self.assertTrue(my_app.check_for_duplicates)

    @patch('pathlib.Path.home')
    def test_no_options(self, home):
        home.return_value = Path(self.temp_base.name)

        my_app = main(["program_name", str(self.output_folder)])
        self.assertEqual(my_app.input_folder, Path(self.output_folder))
        self.assertEqual(my_app.output_folder, Path(self.output_folder))
        self.assertFalse(my_app.convert)
        self.assertTrue(my_app.keep_original_files)
        self.assertFalse(my_app.check_for_small)
        self.assertFalse(my_app.verbose)

    @patch('builtins.print')
    @patch('pathlib.Path.home')
    def test_bad_options(self, home, my_print):
        home.return_value = Path(self.temp_base.name)

        with self.assertRaises(SystemExit) as se:
            main(["program_name", "-Z", str(self.output_folder)])
        self.assertEqual(se.exception.code, 4, 'Invalid option test')
        my_print.assert_called()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
