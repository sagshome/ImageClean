"""
Create an archive for testing
"""
import os, pathlib, sys, tarfile


tarfile_name = '../test/ptest.tar.gz'
tarinput_dir = '/shared/ptest'

if __name__ == '__main__':
    """


    """

    if len(sys.argv) > 3:
        print(f'{sys.argv[0]}: [tar_file_name]:test/ptest.tar.gz [input_directory]: ptest')
        exit(1)
    if len(sys.argv) >= 3:
        tarinput_dir = sys.argv[2]
    if len(sys.argv) >= 2:
        tarfile_name = sys.argv[1]

    if not os.path.exists(tarinput_dir):
        print(f'{sys.argv[0]}: input_directory: {tarinput_dir} does not exist')
        exit(2)

    input_dir = pathlib.Path(tarinput_dir)
    if not input_dir.is_dir():
        print(f'{sys.argv[0]}: input_directory: {tarinput_dir} is not a directory')
        exit(3)

    try:
        tar = tarfile.open(tarfile_name, 'w:gz')
        os.chdir(input_dir)
        for entry in input_dir.iterdir():
            print(f'Adding... {entry.name}')
            tar.add(entry.name)
        tar.close()
    except FileNotFoundError as e:
        print(f'{sys.argv[0]}: tar_file_name: {tarfile_name} can not be created')
        exit(4)

    print('Completed')
    exit(0)
