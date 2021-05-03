#!/usr/bin/env bash

set -ex
pushd ~/MSApublic
git remote update
CURRENT_STATUS=$(git status -uno)
if [[ $CURRENT_STATUS == *"is behind"* ]]; then
  git pull
  systemctl restart MSA
fi
