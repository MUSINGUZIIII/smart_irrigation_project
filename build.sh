#!/usr/bin/env bash
# build.sh

set -o errexit

pip install -r requirements.txt

mkdir -p media/profile_pics
mkdir -p accounts/static/
python manage.py collectstatic --noinput
python manage.py makemigrations --noinput
python manage.py migrate

