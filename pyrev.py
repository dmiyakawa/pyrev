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

'''
Core functionalities for pyrev = Py:Re:VIEW.

Note to developers:
Though some functions starts with "_" (_log_debug()) and some do not,
any functions may change in the future anyway.
You're be warned! X-(
sorry.
'''

import os
import re
import shutil
import yaml

r_chap = re.compile(r'^(?P<level>=+)(?P<column>[column]?)'
                    r'(?P<sp>\s*)(?P<title>.+)$')

r_re = re.compile(r'^(.+.re)$')

from logging import getLogger, NullHandler

local_logger = getLogger(__name__)
local_logger.addHandler(NullHandler())

def _verify_filename(source_dir, filename, logger=local_logger):
    '''
    Checks if a given file is appropriate to use in drivers.
    Returns an absolute path for the filename. None otherwise.
    '''
    abs_path = os.path.abspath(os.path.join(source_dir, filename))
    if source_dir not in abs_path:
        logger.warn(u'"{}" does not point to file in dir "{}". Ignoring.'
                    .format(filename, source_dir))
        return None
    if not os.path.exists(abs_path):
        logger.warn(u'"{}" does not exist in "{}". Ignoring.'
                    .format(filename, source_dir))
        return None
    if os.path.islink(abs_path):
        logger.warn(u'"{}" is a symlink. Ignore.'.format(filename))
        return None
    return abs_path


def _verify_re_filename(source_dir, filename, logger=local_logger):
    '''
    In addition to _is_appropriate_file(), checks if the file name
    looks like a Re:VIEW file (i.e. if the extension is ".re").
    '''
    m = r_re.match(filename)
    if not m:
        logger.debug(u'{} does not look like .re file'.format(filename))
        return None
    return _verify_filename(source_dir, filename)


def _is_appropriate_file(source_dir, filename):
    return _verify_filename(source_dir, filename) is not None


def _is_appropriate_re_file(source_dir, filename):
    return _verify_re_filename(source_dir, filename) is not None


class ReVIEWProject(object):
    '''
    Represents a whole Re:VIEW project in a single directory,
    which should contain config.yml, catalog.yml, etc.
    '''
    RELATED_FILES = set(['config.yml', 'config.yaml',
                         'catalog.yml', 'catalog.yaml',
                         'CHAPS', 'PREDEF', 'POSTDEF', 'PART'])

    # Bookmark keys
    # Bookmark has information about each part, chapter, section, etc.
    # Note: this structure derives from pdftk's dump_data_utf8 subcommand.
    #
    # Bookmark should have a title each author (or editor) will specify.
    BM_TITLE = 'title'
    # Bookmark should have a level. 1 origin.
    # If there's no part specified in the Re:VIEW project, a level for
    # each chapter will be 1, that for each section will be 2, and so on.
    # If there are parts in the book, levels for chapters, sections etc. will
    # be incremented by 1. Each part will have level 1 instead.
    BM_LEVEL = 'level'
    # Bookmark for chapters, sections, etc. will be stored by a single file.
    # This points to which source (.re) file contains it.
    # None if the bookmark is a part.
    # Be careful: non-chapters have this value because they are not part,
    # but they do not have chap_index below.
    BM_SOURCE_FILE_NAME = 'source_file_name'
    # Index of the chapter in a specified source (.re) file.
    # 0-origin.
    # None if the bookmark is not a chapter.
    # This means sections will always contain None for chap_index.
    #
    # Behind the scenes:
    # Re:VIEW has several chapters in a single source file, and we
    # sometimes we want to know which chapter is the first chapter in the file.
    # This will help us to search it.
    BM_SOURCE_CHAP_INDEX = 'source_chap_index'

    # Spaces between chap level ('===') and actual title.
    BM_SP = 'sp'
    # True if column. False (or None) otherwise.
    BM_IS_COLUMN = 'is_column'

    def __init__(self, source_dir, **kwargs):
        self.reset()
        self.init(source_dir, **kwargs)

    def reset(self):
        # Where the whole source files are.
        self.source_dir = None
        self._catalog_files = []
        # Contains all the chapter files for this project,
        # including predef/postdef files.
        # Each name does not contain source_dir part.
        self.source_filenames = []

        self.predef_filenames = []
        self.postdef_filenames = []

        # Either self.parts or self.chaps is available. NOT both.
        # When PART (in catalog.yml or as a single file) is available,
        # self.parts will contain part title and
        # relevant chaps for the part
        # e.g.
        # self.parts = [('Part1', ['chap1.re', 'chap2.re']),
        #               ('Part2', ['chap3.re', 'chap4.re'])]
        # Otherwise self.chaps contains all the relevant chapters.
        # e.g.
        # self.chaps = ['chap1.re', 'chap2.re', 'chap3.re', 'chap4.re']
        self.parts = None
        self.chaps = None

        # Should have correct file name for config.yml (e.g. u'config.yml')
        self.config_file_name = None

        self.title = u''
        self.author = u''
        self.description = u''
        self.coverimage = u''
        self.pdf_num_pages = 0

        # A list of bookmarks representing parts/chapters/sections, etc.
        # Each bookmark is actually a plain dict with BM_XXX keys.
        self.bookmarks = None
        # Shortcut to bookmark (only for chapters).
        # key: (source_file, chap_index)
        #
        # value: bookmark
        # chap_index must not be None
        self.chap_to_bookmark = None

        # Not ready until init() is finished successfully.
        self.ready = False

    def init(self, source_dir, **kwargs):
        '''
        Initializes this instance. Returns True when successful.

        Returns True when successful.
        Returns False otherwise, where this instance will not be usable.
        '''
        logger = kwargs.get('logger') or local_logger
        logger.debug('init()')
        self.logger = logger
        self.source_dir = source_dir

        first_candidate = kwargs.get('first_candidate')
        if not self._find_and_parse_review_config(first_candidate):
            logger.info(u'Failed to find config.yml or relevant.')
            return False

        # Just for debugging.
        assert self.bookname is not None
        assert self.review_config_name is not None

        # Look for "catalog.yml" or legacy old catalog files.
        self._recognize_catalog_files()
        if (not self.parts) and (not self.chaps):
            self.logger.info(u'Failed to recognize book structure in {}.'
                             .format(source_dir))
            return False
        assert (not self.parts) or (not self.chaps)

        # TODO: Check more..

        self._log_debug()

        self.ready = True
        return True

    def _find_and_parse_review_config(self, first_candidate=None, logger=None):
        if not logger: logger = self.logger
        candidates = ['config.yml', 'config.yaml',
                      'sample.yml', 'sample.yaml']
        if first_candidate:
            # Should be evaluated first.
            candidates.insert(0, first_candidate)
            # Remove dup without breaking list order.
            candidates = sorted(set(candidates), key=candidates.index)
        # Iterates possible files and try parsing them.
        # When one looks config file, we use it silently.
        for candidate in candidates:
            if self._try_parse_review_config(candidate):
                logger.debug(u'"{}" is used as Re:VIEW config file.'
                             .format(candidate))
                return True
        return False

    def _try_parse_review_config(self, candidate):
        '''
        Try parsing a given config file (e.g. config.yml) and
        check if it is really an appropriate config for Re:VIEW.
        If it looks appropriate, set up member variables too.
        '''
        self.logger.debug(u'_try_parse_config_yml({})'.format(candidate))
        candidate_path = os.path.join(self.source_dir, candidate)
        if not os.path.isfile(candidate_path):
            return False
        try:
            yaml_data = yaml.safe_load(open(candidate_path))
            if yaml_data.has_key(u'bookname'):
                self.bookname = yaml_data[u'bookname']
                self.review_config_name = candidate
                self.yaml_data = yaml_data

                # Followings are considered to be all optional in driver.
                self.title = yaml_data.get(u'booktitle', u'')
                self.author = yaml_data.get(u'aut')
                self.description = yaml_data.get(u'description', u'')
                self.coverimage = yaml_data.get(u'coverimage', u'')
                return True
        except Exception as e:
            self.logger.info(u'Error during parsing {}: {}'
                             .format(candidate, e))
        return False


    def _recognize_catalog_files(self):
        '''
        Scans catalogue files and detect book structure.
        '''
        self.logger.debug(u'_recognize_catalog_files()')
        if self._recognize_new_catalog_files():
            return True
        self.logger.debug(u'Try recognizing legacy catalog files.')
        return self._recognize_legacy_catalog_files()

    def _recognize_new_catalog_files(self):
        logger = self.logger
        filename = 'catalog.yml'
        catalog_yml_path = _verify_filename(self.source_dir, filename)
        if not catalog_yml_path:
            filename = 'catalog.yaml'
            catalog_yml_path = _verify_filename(self.source_dir, filename)
            if not catalog_yml_path:
                return False

        self._catalog_files.append(filename)
        yaml_data = yaml.load(open(catalog_yml_path))
        if not yaml_data.has_key('CHAPS'):
            return False
        if (type(yaml_data['CHAPS']) is not list
            or len(yaml_data['CHAPS']) == 0):
            return False

        try:
            if yaml_data.get('PREDEF'):
                for filename in map(lambda x: x.strip(), yaml_data['PREDEF']):
                    if not _is_appropriate_file(self.source_dir, filename):
                        logger.debug(u'Ignoring {}'.format(filename))
                        continue
                    self.predef_filenames.append(filename)
                    self.source_filenames.append(filename)
        except:
            # This may happen when PREDEF contains inappropriate data.
            logger.waring('Failed to parse PREDEF. Ignoring..')

        chap = yaml_data['CHAPS'][0]
        if type(chap) is dict:
            logger.debug('Considered to be chaps-with-part structure')
            # Considered to be chaps with part.
            # e.g.
            # CHAPS:
            #   - {"First PART": [ch01.re, ch02.re]}
            #   - {"Second PART": [ch03.re, ch04.re]}
            #
            # Each dictionary must contain just one entry.
            # Otherwise Re:VIEW itself messes up everything :-P
            self.chaps = None
            self.parts = []
            for part_content in yaml_data['CHAPS']:
                if len(part_content) != 1:
                    logger.info(u'Malformed PART content: "{}"'
                                .format(part_content))
                    return False
                (part_title, part_chaps) = part_content.iteritems().next()
                if (type(part_title) is not str
                    and type(part_title) is not unicode):
                    logger.info(u'Malformed PART title: "{}"'
                                .format(part_title))
                    return False
                # Check if all the chap file names are sane.
                if not reduce(lambda x, y: x and
                              ((type(y) is str or (type(y) is unicode))
                               and _is_appropriate_re_file(self.source_dir, y)),
                               part_chaps, True):
                    logger.info(u'Malformed chaps exist in PART: {}'
                                .format(part_chaps))
                    return False
                self.parts.append((part_title, part_chaps))
                for filename in part_chaps:
                    self.source_filenames.append(filename)
        else:
            logger.debug('Considered to be plain chaps structure')
            self.chaps = []
            self.parts = None
            try:
                for filename in map(lambda x: x.strip(), yaml_data['CHAPS']):
                    if not _is_appropriate_re_file(self.source_dir, filename):
                        logger.debug(u'Ignoring {}'.format(filename))
                        continue
                    self.chaps.append(filename)
                    self.source_filenames.append(filename)
            except:
                logger.error('Failed to parse CHAPS. Exitting')
                return False

        try:
            if yaml_data.get('POSTDEF'):
                for filename in map(lambda x: x.strip(), yaml_data['POSTDEF']):
                    if not _is_appropriate_file(self.source_dir, filename):
                        logger.debug(u'Ignoring {}'.format(filename))
                        continue
                    self.postdef_filenames.append(filename)
                    self.source_filenames.append(filename)
        except:
            logger.waring('Failed to parse POSTDEF. Ignoring..')

        return True

    def _recognize_legacy_catalog_files(self):
        '''
        Tries recognizing old catalog files (CHAPS, PREDEF, POSTDEF, PART)
        which has been used before Re:VIEW version 1.3.
        '''
        logger = self.logger
        # First check if at least "CHAPS" file exists or not.
        # If not, abort this procedure immediately.
        chaps_path = _verify_filename(self.source_dir, 'CHAPS')
        if not chaps_path:
            self.logger.error('No valid CHAPS file is available.')
            return False
        self._catalog_files.append('CHAPS')

        # After checking CHAPS existence, we handle PREDEF before actually
        # looking at CHAPS content, to let the system treat .re files in
        # PREDEF before ones in CHAPS.
        if _is_appropriate_file(self.source_dir, 'PREDEF'):
            self._catalog_files.append('PREDEF')
            predef_path = os.path.join(self.source_dir, 'PREDEF')
            for line in file(predef_path):
                filename = line.rstrip()
                if not filename:
                    continue
                if not _is_appropriate_file(self.source_dir, filename):
                    logger.debug(u'Ignore {}'.format(filename))
                    continue
                self.predef_filenames.append(filename)
                self.source_filenames.append(filename)

        # Now handle CHAPS and PART.
        part_titles = None
        part_path = _verify_filename(self.source_dir, 'PART')
        if part_path:
            logger.debug('Valid PART file exists ({})'.format(part_path))
            part_titles = self._detect_parts(file(part_path))
            logger.debug('part_titles: {}'.format(part_titles))

        if part_titles:
            # If PART contains one or more part titles, treat it appropriately.
            # Note: PART may be just empty while the file itself exists.
            logger.debug('Valid part information found.')
            # PART file is available.
            self.parts = []
            self.chaps = None

            current_part = 0
            chaps = []
            for line in file(chaps_path):
                filename = line.rstrip()
                # If empty line appears in CHAPS.
                if not filename:
                    if current_part < len(part_titles):
                        self.parts.append((part_titles[current_part], chaps))
                        current_part += 1
                        chaps = []
                    else:
                        # If there's no relevant part name, ReVIEW will
                        # just ignore the empty line, and thus all the
                        # remaining chapters will be part of the last part.
                        pass
                else:
                    if not _is_appropriate_re_file(self.source_dir, filename):
                        logger.debug(u'Ignore {}'.format(filename))
                        continue
                    # Insert the chapter into internal structures.
                    chaps.append(filename)
                    self.source_filenames.append(filename)
            self.parts.append((part_titles[current_part], chaps))
        else:
            logger.debug('No valid part information found.')
            self.parts = None
            self.chaps = []
            for line in file(chaps_path):
                filename = line.rstrip()
                if not filename:
                    continue
                if not _is_appropriate_re_file(self.source_dir, filename):
                    logger.debug(u'Ignore {}'.format(filename))
                    continue
                self.chaps.append(filename)
                self.source_filenames.append(filename)

        if _is_appropriate_file(self.source_dir, 'POSTDEF'):
            self._catalog_files.append('POSTDEF')
            postdef_path = os.path.join(self.source_dir, 'POSTDEF')
            for line in file(postdef_path):
                filename = line.rstrip()
                if not filename:
                    continue
                if not _is_appropriate_file(self.source_dir, filename):
                    logger.debug(u'Ignore {}'.format(filename))
                    continue
                self.postdef_filenames.append(filename)
                self.source_filenames.append(filename)

        return True
        
    def _detect_parts(self, part_content):
        part_titles = []
        for line in part_content:
            part_titles.append(line.rstrip())
        return part_titles

    def parse_source_files(self, logger=None):
        '''
        Parsees all Re:VIEW files and prepare internal structure.
        '''
        logger = logger or self.logger
        if self.parts is None and self.chaps is None:
            logger.error('No chaps/parts information is available.')
            return None
        logger.debug(u'parse_source_files()')
        self.bookmarks = []
        self.chap_to_bookmark = {}
        for filename in self.predef_filenames:
            self.parse_single_source_file(filename, 0)
        if self.parts:
            for part in self.parts:
                part_title, part_chaps = part
                self._append_bookmark({self.BM_LEVEL: 1,
                                       self.BM_TITLE: part_title.strip(),
                                       self.BM_SOURCE_FILE_NAME: None,
                                       self.BM_SOURCE_CHAP_INDEX: None})
                for chap in part_chaps:
                    self.parse_single_source_file(chap, 1)
        else: # no parts
            for chap in self.chaps:
                self.parse_single_source_file(chap, 0)
        for filename in self.postdef_filenames:
            self.parse_single_source_file(filename, 0)
        return True

    def parse_single_source_file(self, filename, base_level):
        '''
        Parses a single source (.re) file.
        Returns a ParseResult object.
        The object may be from "parse_result" argument (if not None),
        or newly created one (if None)

        This may raises Exceptions when the file looks broken and cannot
        recover the failure.
        '''
        f = file(os.path.normpath(
                u'{}/{}'.format(self.source_dir, filename)))
        chap_index = 0
        for line in f:
            # BOM matters. Force ignore it..
            line = unicode(line, 'utf-8-sig').rstrip()
            m = r_chap.match(line)
            if m:
                level = len(m.group('level'))
                title = m.group('title')
                if level == 1:
                    # If it is a chapter, we set BM_SOURCE_CHAP_INDEX and
                    # increment it by one.
                    new_bookmark = {self.BM_LEVEL: base_level + level,
                                    self.BM_TITLE: title.strip(),
                                    self.BM_SOURCE_FILE_NAME: filename,
                                    self.BM_SOURCE_CHAP_INDEX: chap_index}
                    chap_index += 1
                else:
                    new_bookmark = {self.BM_LEVEL: base_level + level,
                                    self.BM_TITLE: title.strip(),
                                    self.BM_SOURCE_FILE_NAME: filename,
                                    self.BM_SOURCE_CHAP_INDEX: None}        
                self.bookmarks.append(new_bookmark)

    def _append_bookmark(self, bookmark):
        self.bookmarks.append(bookmark)
        bm_source_file_name = bookmark.get(self.BM_SOURCE_FILE_NAME)
        bm_chap_index = bookmark.get(self.BM_SOURCE_CHAP_INDEX)
        if (bm_source_file_name and bm_chap_index is not None):
            key = (bm_source_file_name, bm_chap_index)
            self.chap_to_bookmark[key] = bookmark

    def remove_tempfiles(self, logger=None):
        '''
        Removes possible tempfiles from the project.
        '''
        logger = logger or self.logger
        bookname = self.bookname or u'book'
        temp_dirs = map(lambda x: x.format(bookname),
                        [u'{}', u'{}-pdf', u'{}-epub', u'{}-log'])
        for temp_dir in temp_dirs:
            dir_path = os.path.join(self.source_dir, temp_dir)
            shutil.rmtree(dir_path, ignore_errors=True)

    def has_part(self):
        if self.parts:
            return True
        else:
            return False

    def _log_debug(self, logger=None):
        logger = logger or self.logger
        logger.debug(u'catalog_files: {})'.format(self._catalog_files))
        logger.debug(u'source_filenames(len: {}): {}'
                     .format(len(self.source_filenames), self.source_filenames))
        logger.debug(u'predef_filenames(len: {}): {}'
                     .format(len(self.predef_filenames), self.predef_filenames))
        logger.debug(u'postdef_filenames(len: {}): {}'
                     .format(len(self.postdef_filenames),
                             self.postdef_filenames))
        if self.parts:
            logger.debug(u'parts: {}'.format(self.parts))
        elif self.chaps:
            logger.debug(u'chaps: {}'.format(self.chaps))
        else:
            logger.debug(u'No parts or chaps')
        logger.debug(u'Re:VIEW config file: "{}"'
                     .format(self.review_config_name))

    def _format_bookmark(self, bookmark):
        return ((u'{} "{}"'
                u' (source: {}, index: {}')
                .format('='*bookmark.get(self.BM_LEVEL, 10),
                        bookmark[self.BM_TITLE],
                        bookmark.get(self.BM_SOURCE_FILE_NAME),
                        bookmark.get(self.BM_SOURCE_CHAP_INDEX)))

    def _log_bookmarks(self, logger=None):
        if not logger: logger = self.logger
        if self.bookmarks:
            logger.debug(u'Bookmarks:')
            for i, bookmark in enumerate(self.bookmarks):
                logger.debug(u' {}:{}'.format(i,
                                              self._format_bookmark(bookmark)))
        else:
            logger.debug(u'No bookmark')
        if self.chap_to_bookmark:
            logger.debug(u'chap_to_bookmark:')
            for key in sorted(self.chap_to_bookmark.keys()):
                bookmark = self.chap_to_bookmark[key]
                self.logger.debug(u' {}: "{}"'
                                  .format(key, bookmark[self.BM_TITLE]))

    @classmethod
    def _look_for_base(cls, base_dir, depth, func):
        files = os.listdir(base_dir)
        if func(files):
            return base_dir
        if depth == 0:
            return None
        elif depth > 0:
            depth = depth -1
        for filename in files:
            next_path = os.path.join(base_dir, filename)
            if os.path.isdir(next_path):
                ret = cls._look_for_base(next_path, depth, func)
                if ret:
                    return ret
        return None

    @classmethod
    def _look_for_related_files(cls, base_dir, depth):
        func = lambda files: bool(set(files) & cls.RELATED_FILES)
        return cls._look_for_base(base_dir, depth, func)

    @classmethod
    def _look_for_re_files(cls, base_dir, depth):
        func = lambda files: bool(filter(lambda f: f.endswith('.re'), files))
        return cls._look_for_base(base_dir, depth, func)

    @classmethod
    def guess_source_dir(cls, base_dir, depth=-1):
        '''
        Tries to find Re:VIEW's source directory (source_dir) under "base_dir".
        Returns the path when successful.
        Returns None on failure.

        If depth is set 0 or positive, this function will
        traverse directories until that depth.
        0 means no traverse. 1 means directories in the
        root will be traversed.
        Negative value means no limit for the search depth.

        For example if a project has a following structure:

         project
         |-- README.md
         `-- article
             |-- catalog.yml
             |-- config.yml
             |-- images
             |   `-- cover.jpg
             |-- layouts
             |   `-- layout.erb
             |-- sty
             |   `-- reviewmacro.sty
             |-- style.css
             `-- review_article.re

        .. this function should receive a path to the project and
        return "(path-to-the-project)/article/".
        When depth is set to 0, this will fail to find the directory instead.
        '''
        return (cls._look_for_related_files(base_dir, depth)
                or cls._look_for_re_files(base_dir, depth))


