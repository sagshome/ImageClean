#!/usr/bin/bash

dir=`pwd`
cd ~/PycharmProjects/ImageClean
source venv3.8/bin/activate

coverage run -m pytest backend Utilities
pylint backend Utilities
coverage report -m

cd $dir
