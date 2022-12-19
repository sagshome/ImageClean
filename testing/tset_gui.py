import os
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from ImageCleanUI import DismissDialog


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


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
