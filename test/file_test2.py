#!/usr/bin/env python3
"""
Create an archive for testing
"""
import os, pathlib, sys, tarfile, tempfile, shutil


tarfile_name = 'ptest.tar.gz'
tarinput_dir = '/shared/ptest'

if __name__ == '__main__':
    """


    """

    testcase = pathlib.Path(sys.argv[0])
    test_name = testcase.name[0:len(testcase.name) - len(testcase.suffix)]
    result_file = f'{testcase.parent}{os.path.sep}file_test1.result'

    tar = tarfile.open(tarfile_name)
    start_dir = pathlib.Path(os.getcwd())
    temp_input = tempfile.TemporaryDirectory()
    temp_output = tempfile.TemporaryDirectory()
    temp_file_dir = tempfile.TemporaryDirectory()
    temp_file = f'{temp_file_dir.name}{os.path.sep}find'
    log_file = f'{temp_file_dir.name}{os.path.sep}log'
    print(f'{test_name}:Logs in {temp_file_dir}')

    executable = f'{start_dir.parent}/image_clean.py -r -V -P -o{temp_output.name} {temp_input.name}'
    again = f'{start_dir.parent}/image_clean.py -V -P -o{temp_output.name} {temp_input.name}'

    os.chdir(temp_input.name)
    tar.extractall()
    tar.close()

    result = os.system(f'python3 {executable} > {log_file}')
    if result == 0:
        result = os.system(f'python3 {again} >> {log_file}')
        if result == 0:
            os.chdir(temp_output.name)
            os.system(f'find . -type f > {temp_file}')

            os.chdir(temp_file_dir.name)
            os.system(f'sort {temp_file} > new')
            os.system(f'sort {result_file} > old')

            result = os.system(f'diff old new >> {log_file}')

    print(f'Completed {test_name} - {result}')
    os.chdir(start_dir)
    if result == 0:
        temp_file_dir.cleanup()
        temp_input.cleanup()
        temp_output.cleanup()
    exit(int(result == 0))
