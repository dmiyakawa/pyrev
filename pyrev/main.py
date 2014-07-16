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

u'''\
Py-Re:VIEW: A Re:VIEW tool written in Python.
'''

from __future__ import print_function

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from logging import getLogger, StreamHandler
from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG

from parser import Parser, ParseProblem
from project import ReVIEWProject

import os
import sys
import traceback

VERSION='0.28'

def lint(args):
    logger = getLogger(__name__)
    handler = StreamHandler()
    logger.setLevel(args.log.upper())
    handler.setLevel(args.log.upper())
    logger.addHandler(handler)
    logger.debug('Start running')

    if args.unacceptable_level == 'CRITICAL':
        unacceptable_level = CRITICAL
    elif args.unacceptable_level == 'ERROR':
        unacceptable_level = ERROR
    elif args.unacceptable_level == 'WARNING':
        unacceptable_level = WARNING
    elif args.unacceptable_level == 'INFO':
        unacceptable_level = INFO
    elif args.unacceptable_level == 'DEBUG':
        unacceptable_level = DEBUG
    else:
        raise RuntimeError(u'Unknown level "{}"'
                           .format(args.unacceptable_level))

    file_path = os.path.abspath(args.filename)

    if not os.path.exists(file_path):
        logger.error(u'"{}" does not exist'.format(args.filename))
        return

    elif os.path.isdir(file_path):
        logger.debug(u'"{}" is a directory.'.format(file_path))
        source_dir = ReVIEWProject.guess_source_dir(file_path)
        logger.debug(u'source_dir: {}'.format(source_dir))
        if not source_dir:
            logger.error(u'Failed to detect source_dir')
            return
        project = ReVIEWProject(source_dir, logger=logger)
        project.parse_source_files()
        try:
            parser = Parser(project=project,
                            ignore_threshold=INFO,
                            abort_threshold=unacceptable_level,
                            logger=logger)
            for filename in project.source_filenames:
                logger.debug('Parsing "{}"'.format(filename))
                path = os.path.normpath(u'{}/{}'.format(project.source_dir,
                                                        filename))
                parser.parse_file(path, 0, filename)
                dump_func = lambda x: sys.stdout.write(u'{}\n'.format(x))
                parser._dump(dump_func=dump_func)
        except ParseProblem:
            logger.error(traceback.format_exc())
    else:
        logger.debug(u'"{}" is a file. Interpret a single script.'
                     .format(args.filename))
        try:
            source_dir = os.path.dirname(file_path)
            project = ReVIEWProject(source_dir, logger=logger)
            project.parse_source_files()

            parser = Parser(project=project,
                            ignore_threshold=INFO,
                            abort_threshold=unacceptable_level,
                            logger=logger)
            source_name = os.path.basename(args.filename)
            parser.parse_file(args.filename, 0, source_name)
            dump_func = lambda x: sys.stdout.write(u'{}\n'.format(x))
            parser._dump(dump_func=dump_func)
        except ParseProblem:
            logger.error(traceback.format_exc())


def lintstr(args):
    pass


def main():
    parser = ArgumentParser(description=(__doc__),
                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('filename')
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
    parser.add_argument('-u', '--unacceptable_level',
                        action='store',
                        default='CRITICAL',
                        help=(u'Error level that aborts the check.'))
    args = parser.parse_args()
    lint(args)


def devel():
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

    args = parser.parse_args()
    if args.debug:
        args.log = 'DEBUG'
    args.func(args)


if __name__ == '__main__':
    main()
