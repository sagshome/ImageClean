#!/usr/bin/bash


#Best run from the pycharm terminal,  it will source the virtual environment
#dir=`pwd`
#cd ~/PycharmProjects/ImageClean
#source venv3.8/bin/activate

coverage run -m pytest backend Utilities image_cleaner.py
pylint backend Utilities image_cleaner.py
coverage report -m

#cd $dir
