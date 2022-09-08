import unittest

from Backend.Cleaner import Cleaner, ImageClean

class SetterTest(unittest.TestCase):

    def setUp(self):
        self.app = ImageClean('test_app')

    def test_one(self):
        self.assertEqual(self.app.app_name, 'test_app', "Failed to set the app name")


if __name__ == '__main__':
    unittest.main()