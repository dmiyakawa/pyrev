#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014 Daisuke Miyakawa d.miyakawa@gmail.com
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from logging import getLogger, StreamHandler

from main import lint
from project import ReVIEWProject
from version import VERSION

import utils

import os
import shutil
import sys


def lintstr(args, logger):
    pass


def copy_chapter(args, logger):
    '''
    Copy a chapter from source to dest. Also copies relevant images.

    src must be a specific file in a project
    dst can be a directory or a file, whose name may be different from
    the original.
    '''
    return utils.copy_document(args.src, args.dst, logger)


def devel():
    '''
    Another entrance for pyrev. Available with pyrev-devel.
    '''
    parser = ArgumentParser(description=(__doc__),
                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('--log',
                        default='INFO',
                        help=('Set log level. e.g. DEBUG, INFO, WARN'))
    parser.add_argument('-d', '--debug',
                        action='store_true',
                        help=('Aliased to --log=DEBUG'))
    parser.add_argument('-v', '--version',
                        action='version',
                        version=u"%(prog)s {}".format(VERSION),
                        help=u'Show version and exit.')
    subparsers = parser.add_subparsers()

    # Lint
    parser_lint = subparsers.add_parser('lint', help='Do lint check')
    parser_lint.add_argument('filename')
    parser_lint.add_argument('-u', '--unacceptable_level',
                             action='store',
                             default='CRITICAL',
                             help=(u'Error level that aborts the check.'))
    parser_lint.set_defaults(func=lint)

    parser_lintstr = subparsers.add_parser('lintstr',
                                           help='Check a given string')
    parser_lintstr.set_defaults(func=lintstr)

    # Copy-Document
    parser_ic = subparsers.add_parser('copy-document',
                                      help='Copy a single document')
    parser_ic.add_argument('src')
    parser_ic.add_argument('dst')
    parser_ic.set_defaults(func=copy_chapter)

    args = parser.parse_args()
    if args.debug:
        args.log = 'DEBUG'

    logger = getLogger(__name__)
    handler = StreamHandler()
    logger.setLevel(args.log.upper())
    handler.setLevel(args.log.upper())
    logger.addHandler(handler)

    return args.func(args, logger)


if __name__ == '__main__':
    ret = devel()
    if ret != 0:
        sys.exit(ret)
