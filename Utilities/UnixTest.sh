#!/usr/bin/bash

dir=`pwd`
cd ~/ImageClean
source unix/bin/activate

coverage run -m pytest Backend
pylint Backend
coverage report -m

cd $dir
