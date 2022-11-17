#!/usr/bin/bash

dir=`pwd`
cd ~/PycharmProjects/ImageClean
source venv3.8/bin/activate

coverage run -m pytest backend Utilities
pylint backend UI Utilities
coverage report -m

cd $dir
