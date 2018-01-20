#!/bin/sh
pushd /home/centos/dci-rhel-feeder
git fetch -a
git checkout master
git reset --hard origin/master
rm -rf venv
python -m virtualenv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
source ./dcirc.sh
python add-nightly-rhel-image.py 7
python add-nightly-rhel-image.py 8
deactivate
popd