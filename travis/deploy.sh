#!/bin/bash -e

DEPLOY=false
FINAL=false
BUILD_TAG=false # for rc

if [[ ${TRAVIS_BRANCH} =~ ^(master|[0-9].[0-9])$ ]] && [ ${TRAVIS_PULL_REQUEST} == false ]
then
    DEPLOY=true
fi

if [[ ${TRAVIS_TAG} =~ ^[0-9].[0-9]+.[0-9]$ ]]
then
    if [ ${TRAVIS_TAG} != $(python setup.py -V) ]
    then
        echo "The tag name doesn't match with the egg version."
        exit 1
    fi
    DEPLOY=true
    FINAL=true
fi

if [[ ${TRAVIS_TAG} =~ ^[0-9].[0-9]+.0rc[0-9]$ ]]
then
    VERSION=`echo ${TRAVIS_TAG} | awk -Frc '{print $1}'`
    if [ ${VERSION} != $(python setup.py -V) ]
    then
        echo "The tag name doesn't match with the egg version."
        exit 1
    fi
    DEPLOY=true
    BUILD_TAG=rc`echo ${TRAVIS_TAG} | awk -Frc '{print $2}'`
fi

if [ ${DEPLOY} == true  ] && [ ${TRAVIS_PYTHON_VERSION} == "2.7" ]
then
    echo "[distutils]" > ~/.pypirc
    echo "index-servers = c2c-internal" >> ~/.pypirc
    echo "[c2c-internal]" >> ~/.pypirc
    echo "username:${PIP_USERNAME}" >> ~/.pypirc
    echo "password:${PIP_PASSWORD}" >> ~/.pypirc
    echo "repository:http://pypi.camptocamp.net/internal-pypi/simple" >> ~/.pypirc

    set -x

    if [ ${BUILD_TAG} != false ]
    then
        .build/venv/bin/python setup.py egg_info --no-date --tag-build "${BUILD_TAG}" sdist upload -r c2c-internal
    else
    if [ ${FINAL} == true ]
        then
            .build/venv/bin/python setup.py egg_info --no-date --tag-build "" bdist_wheel upload -r c2c-internal
        else
            .build/venv/bin/python setup.py bdist_wheel upload -r c2c-internal
        fi
    fi
fi
