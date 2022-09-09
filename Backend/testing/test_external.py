import os
import sys
import tarfile
import tempfile
import unittest

from pathlib import Path
from typing import Optional

sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))

"""
Create an archive for testing
"""

my_location = Path(os.path.dirname(__file__))
os.unsetenv('CLEANER_DEBUG')  # Force off DEBUG logging


class ExternalSetup(unittest.TestCase):

    def setUp(self):
        self.tarfile_name = None  # This is what is used for input
        self.results_file = None  # This is what is produced (find . -type f > results_file)
        self.input_file = None  # This is what remains (same find as above)
        self.temp_input = tempfile.TemporaryDirectory()
        self.temp_output = tempfile.TemporaryDirectory()
        self.temp_file_dir = tempfile.TemporaryDirectory()

        self.temp_file = f'{self.temp_file_dir.name}{os.path.sep}find'
        self.log_file = f'{self.temp_file_dir.name}{os.path.sep}log'

        self.results_out = []
        self.results_in = []
        self.diff_out = f'{self.temp_file_dir.name}{os.path.sep}diffout'
        self.diff_in = f'{self.temp_file_dir.name}{os.path.sep}diffin'

        super(ExternalSetup, self).setUp()

    def force_temp_input_to_output(self):
        self.temp_input.cleanup()
        self.temp_input = self.temp_output

    def tearDown(self):
        self.temp_input.cleanup()
        self.temp_output.cleanup()
        self.temp_file_dir.cleanup()
        super(ExternalSetup, self).tearDown()

    def extract(self):
        if self.tarfile_name:
            start_dir = Path(os.getcwd())
            tar = tarfile.open(self.tarfile_name)
            os.chdir(self.temp_input.name)
            tar.extractall()
            tar.close()
            os.chdir(start_dir)

    def execute(self, param: str) -> int:
        executable = f'./Backend/image_clean.py {param} {self.temp_input.name}'
        return os.system(f'python3 {executable} >> {self.log_file}')

    def _iter_dir(self, setlist, folder, base_length):
        for entry in folder.iterdir():
            if entry.is_dir():
                self._iter_dir(setlist, entry, base_length)
            else:
                setlist.add(str(entry)[base_length:])

    @staticmethod
    def _read_dir(setlist, dir_file):
        f = open(dir_file, "r")
        lines = f.read()
        for line in lines.split('\n'):
            if not line == '':
                setlist.add(line)
        f.close()

    def compare(self, duplicates=True, movies=True, migrated=True):
        count = 0
        if self.results_file:
            new = set()
            old = set()
            self._iter_dir(new, Path(self.temp_output.name), len(self.temp_output.name) + 1)
            self._read_dir(old, self.results_file)
            for each in new - old:
                count += 1
                self.results_out.append(f'Unexpected new output file: {each}')
            for each in old - new:
                if (each.startswith('Cleaner_Duplicates') and duplicates) or \
                        (each.startswith('Cleaner_ImageMovies') and movies) or \
                        (each.startswith('Cleaner_Migrated') and migrated):
                    count += 1
                    self.results_out.append(f'Missing expected output file: {each}')
                elif not (each.startswith('Cleaner_Duplicates') or
                          each.startswith('Cleaner_ImageMovies') or
                          each.startswith('Cleaner_Migrated')):
                    count += 1
                    self.results_out.append(f'Missing expected output file: {each}')

        if self.input_file:
            new = set()
            old = set()
            self._iter_dir(new, Path(self.temp_input.name), len(self.temp_input.name) + 1)
            self._read_dir(old, self.input_file)
            for each in new - old:
                count += 1
                self.results_in.append(f'Unexpected file found in input: {each}')
            for each in old - new:
                count += 1
                self.results_in.append(f'Missing expected input file: {each}')
        return count

    def print_results(self):
        if self.results_out:
            print(f'\n{self._testMethodName}: Unexpected Output')
            for element in self.results_out:
                print(element)

        if self.results_in:
            print(f'\n{self._testMethodName}: Unexpected Input')
            for element in self.results_in:
                print(element)


class TestExternal(ExternalSetup):

    def setUp(self):
        super(TestExternal, self).setUp()

    def test_new_import(self):
        self.tarfile_name = my_location.joinpath('data').joinpath('ptest.tar.gz')
        self.results_input = my_location.joinpath('data').joinpath('ptest.input')
        self.results_file = my_location.joinpath('data').joinpath('file_test1.result')
        self.input_file = my_location.joinpath('data').joinpath('full_input.result')  # This is what remains

        self.extract()

        self.assertEqual(self.execute(f'-P -o{self.temp_output.name}'), 0, "Failed to execute")
        self.assertEqual(self.compare(), 0, self.print_results())

    def test_re_import(self):
        self.tarfile_name = my_location.joinpath('data').joinpath('ptest.tar.gz')
        self.results_input = my_location.joinpath('data').joinpath('ptest.input')
        self.results_file = my_location.joinpath('data').joinpath('file_test2.result')
        self.extract()

        self.assertEqual(self.execute(f'-P -o{self.temp_output.name}'), 0, "Failed to execute")
        self.assertEqual(self.execute(f'-P -o{self.temp_output.name}'), 0, "Failed to re-execute")
        self.assertEqual(self.compare(), 0, self.print_results())

    def test_rerun(self):
        self.tarfile_name = my_location.joinpath('data').joinpath('ptest.tar.gz')
        self.results_input = my_location.joinpath('data').joinpath('ptest.input')
        self.results_file = my_location.joinpath('data').joinpath('file_test1.result')
        self.extract()

        self.assertEqual(self.execute(f'-P -o{self.temp_output.name}'), 0, "Failed to execute")
        self.assertEqual(self.execute('-P'), 0, "Failed to rerun")
        self.assertEqual(self.compare(), 0, self.print_results())

    def test_run_no_saves(self):
        self.tarfile_name = my_location.joinpath('data').joinpath('ptest.tar.gz')
        self.results_input = my_location.joinpath('data').joinpath('ptest.input')
        self.results_file = my_location.joinpath('data').joinpath('file_test1.result')
        self.input_file = my_location.joinpath('data').joinpath('file_test1.result')  # This is what remains

        self.extract()
        # os.environ['CLEANER_DEBUG'] = "True"
        self.assertEqual(self.execute(f'-P -o{self.temp_output.name}'), 0, "Failed to execute")
        self.assertEqual(self.execute(''), 0, "Failed to rerun")
        self.force_temp_input_to_output()
        self.assertEqual(self.compare(duplicates=False, movies=False, migrated=False, ), 0, self.print_results())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
