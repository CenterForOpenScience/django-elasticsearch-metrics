#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import os
from setuptools import setup, find_packages


def find_version(fname):
    """Attempts to find the version number in the file names fname.
    Raises RuntimeError if not found.
    """
    version = ""
    with open(fname, "r") as fp:
        reg = re.compile(r'__version__ = [\'"]([^\'"]*)[\'"]')
        for line in fp:
            m = reg.match(line)
            if m:
                version = m.group(1)
                break
    if not version:
        raise RuntimeError("Cannot find version information")
    return version


def read(fname):
    with open(fname) as fp:
        content = fp.read()
    return content


setup(
    name="django-elasticsearch-metrics",
    version=find_version(os.path.join("elasticsearch_metrics", "__init__.py")),
    author="Steven Loria, Dawn Pattison",
    author_email="steve@cos.io, pattison.dawn@cos.io",
    description="Django app for storing time-series metrics in Elasticsearch.",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    url="http://github.com/sloria/django-elasticsearch-metrics",
    license="MIT",
    packages=find_packages(exclude=("tests",)),
    keywords=(
        "django",
        "elastic",
        "elasticsearch",
        "elasticsearch-dsl",
        "time-series",
        "metrics",
        "statistics",
    ),
    install_requires=["elasticsearch-dsl>=6.0.0"],
    classifiers=[
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Framework :: Django",
        "Framework :: Django :: 1.11",
        "Framework :: Django :: 2.0",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    zip_safe=False,
    include_package_data=True,
    project_urls={
        "Issues": "https://github.com/sloria/django-elasticsearch-metrics/issues",
        "Changelog": "https://github.com/sloria/django-elasticsearch-metrics/blob/master/CHANGELOG.md",
    },
)
