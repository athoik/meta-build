#!/bin/sh

setup_git() {
  git config --global user.email "travis@travis-ci.org"
  git config --global user.name "Travis CI"
}

commit_files() {
  git add satellites.xml
  git commit --message "Travis build: $TRAVIS_BUILD_NUMBER"
}

upload_files() {
  git remote add upstream https://${GH_TOKEN}@github.com/athoik/meta-build.git > /dev/null 2>&1
  git push --quiet upstream master || echo 'failed to push with error $?"
}

setup_git
commit_files
upload_files
