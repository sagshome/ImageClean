REM Best run from the pycharm terminal,  it will source the virtual environment

coverage run -m pytest backend Utilities .
pylint backend Utilities image_cleaner.py ImageCleanUI.py
coverage report -m


