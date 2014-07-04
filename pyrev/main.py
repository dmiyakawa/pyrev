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
Py-Re:VIEW
'''

from __future__ import print_function

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from logging import getLogger, StreamHandler
from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG

from parser import Parser, ParseProblem
from pyrev import ReVIEWProject

import os
import sys
import traceback

VERSION='0.2'

def main():
    parser = ArgumentParser(description=(__doc__),
                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('filename')
    parser.add_argument('--log',
                        default='INFO',
                        help=('Set log level. e.g. DEBUG, INFO, WARN'))
    parser.add_argument('--debug',
                        action='store_true',
                        help=('aliased to --log=DEBUG'))
    parser.add_argument('-l', '--level_threshold',
                        action='store',
                        default='CRITICAL',
                        help=(u'Error Level for the check.'
                              u' If everything should be accepted, CRITICAL.'))
    parser.add_argument('-v', '--version',
                        action='version',
                        version=u"%(prog)s {}".format(VERSION),
                        help=u'Show version and exit.')
    args = parser.parse_args()
    if args.debug:
        args.log = 'DEBUG'

    logger = getLogger(__name__)
    handler = StreamHandler()
    logger.setLevel(args.log.upper())
    handler.setLevel(args.log.upper())
    logger.addHandler(handler)
    logger.debug('Start running')
    if args.level_threshold == 'CRITICAL':
        level_threshold = CRITICAL
    elif args.level_threshold == 'ERROR':
        level_threshold = ERROR
    elif args.level_threshold == 'WARNING':
        level_threshold = WARNING
    elif args.level_threshold == 'INFO':
        level_threshold = INFO
    elif args.level_threshold == 'DEBUG':
        level_threshold = DEBUG
    else:
        raise RuntimeError(u'Unknown level "{}"'.format(args.level_threshold))

    if not os.path.exists(args.filename):
        logger.error(u'"{}" does not exist'.format(args.filename))
        return

    elif os.path.isdir(args.filename):
        logger.debug(u'"{}" is a directory. Interprete the whole project'
                     .format(args.filename))
        source_dir = ReVIEWProject.guess_source_dir(args.filename)
        logger.debug(u'source_dir: {}'.format(source_dir))
        project = ReVIEWProject(source_dir, logger=logger)
        project.parse_source_files()
        project._log_bookmarks()
        project._log_debug()
        try:
            parser = Parser(level=level_threshold, logger=logger)
            for filename in project.source_filenames:
                logger.debug('Parsing "{}"'.format(filename))
                path = os.path.normpath(u'{}/{}'.format(project.source_dir,
                                                        filename))
                parser.parse(path, 0, filename)
                dump_func = lambda x: sys.stdout.write(u'{}\n'.format(x))
                parser._dump(dump_func=dump_func)
        except ParseProblem as e:
            logger.error(traceback.format_exc())
            #logger.error(u'{}: {}'.format(type(e).__name__, e))
    else:
        logger.debug(u'"{}" is a file. Interpret a single script.'
                     .format(args.filename))
        try:
            parser = Parser(level=level_threshold, logger=logger)
            source_name = os.path.basename(args.filename)
            parser.parse(args.filename, 0, source_name)
            parser._dump()
        except ParseProblem as e:
            logger.error(traceback.format_exc())
            #logger.error(u'{}: {}'.format(type(e).__name__, e))


if __name__ == '__main__':
    main()
