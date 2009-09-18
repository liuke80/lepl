#!/bin/bash

# IMPORTANT - update version in setup.py

# this generates a new release, but does not register anything with pypi
# or upload files to google code.

# python setup.py sdist --formats=gztar,zip register upload

 
RELEASE=`egrep "version=" setup.py | sed -e "s/.*'\(.*\)'.*/\\1/"`
VERSION=`echo $RELEASE | sed -e "s/.*?\([0-9]\.[0-9]\).*/\\1/"`

sed -i -e "s/release = .*/release = '$RELEASE'/" doc-src/conf.py
sed -i -e "s/version = .*/version = '$VERSION'/" doc-src/conf.py

sed -i -e "s/__version__ = .*/__version__ = '$RELEASE'/" src/lepl/__init__.py

rm -fr dist MANIFEST*

python setup.py sdist --formats=gztar,zip

#./build-doc.sh

rm -fr "LEPL-$RELEASE"
mkdir "LEPL-$RELEASE"
cp -r doc "LEPL-$RELEASE"
tar cvfz "dist/LEPL-$RELEASE-doc.tar.gz" "LEPL-$RELEASE"
zip -r "dist/LEPL-$RELEASE-doc.zip" "LEPL-$RELEASE" -x \*.tgz
rm -fr "LEPL-$RELEASE"

#./push-docs.sh
