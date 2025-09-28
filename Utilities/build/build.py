"""
Generic Build Script,   will activate the virtual env (.venv).
python .../this_file <--force> <virtual_env>
   --force      :will build even if the tests fail
   virtual_env  :to stipulate another virtual environment path,  it still must live at the root of the project path
"""

import os
import sys
import platform

from pathlib import Path

if __name__ == '__main__':  # pragma: no cover
    # pylint: disable=invalid-name
    build_path = Path(os.path.abspath(__file__)).parent
    project_path = build_path.parent.parent
    force = False
    os.chdir(project_path)
    if len(sys.argv) > 1 and sys.argv[1] == '--force':
        force = True
        sys.argv = sys.argv[2:]
    virtual_env = sys.argv[1] if len(sys.argv) == 2 else '.venv'
    coverage_file = str(project_path.joinpath(".coveragerc"))
    pylint_file = str(project_path.joinpath(".pylintrc"))

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
    result = os.system('coverage run -m pytest backend Utilities .')

    # os.system('pylint backend Utilities cmdline.py ImageCleanUI.py')
    result += os.system('pylint backend Utilities cmdline.py')
    result += os.system('coverage report --fail-under=100 -m')
    if result == 0 or force:  # Pyinstaller fails when running fake ubuntu - Minimum required OpenGL version (2.0) NOT found!
        result += os.system('pyinstaller --clean cleaner_cron.spec')
        result += os.system(f'pyinstaller --clean {installer}')
    if result != 0:
        print('Build Failed')
    sys.exit(result)
