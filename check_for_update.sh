#!/usr/bin/env bash

set -ex
pushd /home/pi/MSApublic
git remote update
CURRENT_STATUS=$(git status -uno)
if [[ $CURRENT_STATUS == *"is behind"* ]]; then
  echo "Downloading new version"
  systemctl stop MSA
  git pull
  cmp --silent /home/pi/build/WEB_VERSION WEB_VERSION && echo "No web build change" || echo "Downloading new web build" && aws s3 cp "$(cat WEB_VERSION)" /tmp/web_build.zip && rm -r /home/pi/build && unzip /tmp/web_build.zip -d /home/pi/
  systemctl start MSA
fi
