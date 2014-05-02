#!/usr/bin/env python

from distutils.core import setup

setup(
    name='fixpp',
    version='0.0.1',
    author='secwall',
    author_email='mail@secwall.me',
    py_modules=['fixpp'],
    url='http://github.com/secwall/fixpp',
    license='BSD',
    description='FIX log pretty printer (for QuickFix)',
    long_description='FIX log pretty printer (for QuickFix)',
    zip_safe=False,
    install_requires = [
        "argparse",
        "appdirs",
    ],
    entry_points={
        'console_scripts': [
            'fixpp = fixpp:_main',
        ],
    },
)
