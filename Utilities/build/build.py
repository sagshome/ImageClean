"""
Generic Build Script,   will activate the virtual env.
"""

import os
import sys
import platform

from pathlib import Path


if __name__ == '__main__':  # pragma: no cover
    # pylint: disable=invalid-name
    build_path = Path(os.path.abspath(__file__)).parent
    project_path = build_path.parent.parent
    virtual_env = sys.argv[1] if len(sys.argv) == 2 else 'venv'
    coverage_file = str(build_path.joinpath(".coveragerc"))
    pylint_file = str(build_path.joinpath(".pylintrc"))

    print(f'Project Path:{project_path}\nVirtual Environment:{virtual_env}\n'
          f'Build Scripts:{build_path}\nCoverage File:{coverage_file}')

    if platform.system() == 'Windows':
        activate_this = Path(project_path).joinpath(virtual_env).joinpath('Scripts').joinpath('activate_this.py')
        installer = 'importer-win.spec'
    else:
        activate_this = Path(project_path).joinpath(virtual_env).joinpath('bin').joinpath('activate_this.py')
        installer = 'importer.spec'

    if activate_this.exists():
        with open(activate_this, encoding="utf8") as f:
            code = compile(f.read(), activate_this, 'exec')
            exec(code, dict(__file__=activate_this))  # pylint: disable=exec-used

    os.chdir(project_path)

    result = os.system(f'coverage run --rcfile={coverage_file} -m pytest backend Utilities .')

    # os.system(f'pylint --rcfile={pylint_file} backend Utilities image_cleaner.py ImageCleanUI.py')
    result += os.system(f'pylint --rcfile={pylint_file} backend Utilities image_cleaner.py')
    result += os.system('coverage report --fail-under=100 -m')
    if result == 0:  # Pyinstaller fails when running fake ubuntu - Minimum required OpenGL version (2.0) NOT found!
        result += os.system('pyinstaller cleaner_cron.spec')
        result += os.system(f'pyinstaller {installer}')
    if result != 0:
        print('Build Failed')
    sys.exit(result)
