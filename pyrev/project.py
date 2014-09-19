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

def _verify_filename(source_dir, filename, logger=None):
    '''
    Checks if a given file is appropriate to use in drivers.
    Returns an absolute path for the filename. None otherwise.
    '''
    logger = logger or local_logger
    abs_path = os.path.abspath(os.path.join(source_dir, filename))
    if source_dir not in abs_path:
        logger.info(u'"{}" does not point to file in dir "{}".'
                    .format(filename, source_dir))
        return None
    if not os.path.exists(abs_path):
        logger.info(u'"{}" does not exist in "{}".'
                    .format(filename, source_dir))
        return None
    if os.path.islink(abs_path):
        logger.info(u'"{}" is a symlink.'.format(filename))
        return None
    logger.debug('"{}" is verified as safe'.format(abs_path))
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


def _split_path_into_dirs(path):
    '''
    a/b/c/d.txt -> ['a', 'b', 'c', 'd.txt']
    '''
    (drive, path_and_file) = os.path.splitdrive(path)
    dirs = []
    while True:
        path, _dir = os.path.split(path)

        if _dir:
            dirs.append(_dir)
        else:
            if path:
                dirs.append(path)
            break
    dirs.reverse()
    return dirs


class ProjectImage(object):
    '''
    Right now this class supports two types of image structures.
    1. images/chap1-image1.png
    2. images/chap1/image1.png
    '''

    def __init__(self, rel_path, parent_filename, image_dir):
        self.parent_filename = parent_filename
        (parent_head, parent_tail) = os.path.splitext(parent_filename)
        # chap1.re -> 'chap1'
        self.parent_id = parent_head
        # '.re'
        self.parent_tail = parent_tail
        # e.g. 'images/chap1-image1.png'
        self.rel_path = rel_path
        self.image_dir = image_dir
        parts = _split_path_into_dirs(self.rel_path)
        assert ((len(parts) == 2 or len(parts) == 3)
                and parts[0] == self.image_dir),\
            'rel_path: "{}", image_dir: "{}"'.format(self.rel_path,
                                                     self.image_dir)
        # 'chap1-image1.png' -> ('chap1-image1', '.png')

        if len(parts) == 3:
            # ['images', 'chap1', 'image1.png']
            assert parts[1] == self.parent_id
            (head, tail) = os.path.splitext(parts[2])
            self.id = head
        else:  # len(parts) == 2
            (head, tail) = os.path.splitext(parts[1])
            # e.g. 'chap1-image1' should start with 'chap1-'
            assert head.startswith('{}-'.format(self.parent_id))
            # e.g. 'images/chap1-image1.png' -> image1
            self.id = head[len(self.parent_id)+1:]
        assert self.id
        # '.png'
        self.tail = tail

    def __str__(self):
        return u'{} (parent: {})'.format(self.rel_path,
                                         self.parent_filename)


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

    @staticmethod
    def instantiate(source_dir, **kwargs):
        driver = ReVIEWProject(source_dir,
                               logger=kwargs.get('logger'))
        if driver.init(**kwargs):
            return driver
        else:
            return None

    def __init__(self, source_dir, logger=None):
        # Where the whole source files are.
        self.source_dir = os.path.normpath(source_dir)
        self.logger = logger or local_logger
        self._reset()

    def _reset(self):
        self.config_file = None
        self.catalog_file = None

        # catalog.yml (for newer projects),
        # or CHAPS/PREDEF/POSTDEF etc. (for older projects).
        self._catalog_files = []

        # Contains all chapter files for this project.
        # Each name does not contain source_dir part.
        # This includes files in predef_filenames and postdef_filenames,
        # while it does NOT include possible draft filenames.
        self.source_filenames = []

        self.predef_filenames = []
        self.postdef_filenames = []

        # Possible "draft" files.
        # The "draft" files are re files which are in source_dir, but
        # not included in catalog.yml.
        self.draft_filenames = []

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

        self.image_dir = None
        # Contains a mapping from filenames to images relevant to the files.
        # This will include all mapping including draft filenames.
        # {'chap1.re': [ProjectImage, ...]}
        self.images = {}

        # image files those are not mapped
        self.unmappable_images = []

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

    def init(self,
             config_file=None,
             catalog_file=None,
             logger=None,
             **kwargs):
        '''
        Initializes this instance.
        Returns True when successful.
        Returns False otherwise, where this instance will not be usable.

        config_file: a filename of a review config file.
        catalog_file: a filename of a review catalog file.
        '''
        logger = kwargs.get('logger') or self.logger
        logger.debug(u'ReVIEWProject.init()')

        if config_file:
            logger.debug(u'config_file is specified ("{}"). Try pasing it.'
                         .format(config_file))
            if not self._try_parse_config_file(config_file):
                logger.error('Failed to parse config file "{}"'
                             .format(config_file))
                return False
        else:
            logger.debug('config_file is not specified. Find suitable one.')
            if not self._find_and_parse_config_file():
                logger.info(u'Failed to find config.yml or relevant.')
                return False

        # Just for debugging.
        assert self.bookname is not None
        assert self.config_file is not None

        if catalog_file:
            logger.debug(u'catalog_file is specified ("{}"). Try parsing it.'
                         .format(catalog_file))
            if not self._try_parse_catalog_file(catalog_file):
                logger.error('Failed to parse catalog file "{}"'
                             .format(catalog_file))
                return False
        else:
            logger.debug('catalog_file is not specified. Find suitable one(s).')
            if not self._recognize_catalog_files():
                logger.info(u'Failed to find config.yml or relevant.')
                return False
        
        if (self.parts is None) and (self.chaps is None):
            self.logger.warn(u'Failed to recognize book structure in {}.'
                             .format(self.source_dir))
            return False
        if (not self.parts) and (not self.parts):
            self.logger.info(u'No chapter found.')

        self._recognize_draft_files()

        self.image_dir = kwargs.get('image_dir', 'images')
        self.image_dir_path = os.path.normpath('{}/{}'.format(self.source_dir,
                                                              self.image_dir))
        self.images = {}
        if os.path.isdir(self.image_dir_path):
            self._recognize_image_files()
        else:
            self.logger.info(u'"{}"({}) is not a directory'
                             .format(self.image_dir, self.image_dir_path))

        # TODO: Check more..

        self._log_debug()

        self.ready = True
        return True

    def _find_and_parse_config_file(self, logger=None):
        logger = logger or self.logger
        candidates = ['config.yml', 'config.yaml',
                      'sample.yml', 'sample.yaml']
        # Iterates possible files and try parsing them.
        # When one looks config file, we use it silently.
        for candidate in candidates:
            if self._try_parse_config_file(candidate):
                logger.debug(u'"{}" is used as Re:VIEW config file.'
                             .format(candidate))
                return True
        return False

    def _try_parse_config_file(self, candidate, logger=None):
        '''
        Try parsing a given config file (e.g. config.yml) and
        check if it is really an appropriate config for Re:VIEW.
        If it looks appropriate, set up member variables too.

        Returns True if parsing the file is successful.
        Returns False otherwise.
        '''
        logger = logger or self.logger
        candidate_path = os.path.normpath(os.path.join(self.source_dir,
                                                       candidate))
        if not os.path.isfile(candidate_path):
            logger.error(u'Did not find config_file "{}".'.format(candidate))
            return False
        if self.source_dir not in candidate_path:
            logger.error(u'"{}" is not in source_dir'.format(candidate))
            return False

        try:
            yaml_data = yaml.safe_load(open(candidate_path))
            if yaml_data.has_key(u'bookname'):
                self.bookname = yaml_data[u'bookname']
                self.yaml_data = yaml_data

                # Followings are considered to be all optional in driver.
                self.title = yaml_data.get(u'booktitle', u'')
                self.author = yaml_data.get(u'aut')
                self.description = yaml_data.get(u'description', u'')
                self.coverimage = yaml_data.get(u'coverimage', u'')
                self.config_file = candidate
                return True
        except Exception as e:
            logger.info(u'Error during parsing {}: {}'.format(candidate, e))
        return False

    def _try_parse_catalog_file(self, catalog_file, logger=None):
        '''
        Try parsing a single catalog file, which must be in new format
        (so called "catalog yaml"), not older format
        (with PART/CHAPS/PREDEF/POSTDEF).

        Returns True if parsing the file is successful.
        Returns False otherwise.
        '''
        logger = logger or self.logger
        catalog_yml_path = _verify_filename(self.source_dir, catalog_file,
                                            logger=logger)
        if not catalog_yml_path: return False
        logger.debug(u'catalog_yml path: "{}"'.format(catalog_yml_path))
        yaml_data = yaml.load(open(catalog_yml_path))

        if (not yaml_data.has_key('CHAPS')
            or type(yaml_data['CHAPS']) is not list
            or len(yaml_data['CHAPS']) == 0):
            logger.info(u'CHAPS elem is not appropriate.')
            return False

        predef_filenames = []
        source_filenames = []
        postdef_filenames = []
        source_filenames = []
        parts = None
        chaps = None

        try:
            if yaml_data.get('PREDEF'):
                for filename in map(lambda x: x.strip(), yaml_data['PREDEF']):
                    if not _is_appropriate_file(self.source_dir, filename):
                        logger.info((u'Ignoring "{}" because the file looks'
                                     u' inappropriate'
                                     u' (not available, invalid, etc')
                                    .format(filename))
                        continue
                    predef_filenames.append(filename)
                    source_filenames.append(filename)
        except:
            # This may happen when PREDEF contains inappropriate data.
            logger.waring('Failed to parse PREDEF. Ignoring..')

        # We are sure CHAPS is available since we checked it above.
        chap = yaml_data['CHAPS'][0]
        if type(chap) is dict:
            # e.g.
            # CHAPS:
            #   - {"First PART": [ch01.re, ch02.re]}
            #   - {"Second PART": [ch03.re, ch04.re]}
            #
            # Assume each dictionary must contain just one entry.
            logger.debug(u'Considered to be chaps-with-part structure.')
            chaps = None
            parts = []
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
                parts.append((part_title, part_chaps))
                for filename in part_chaps:
                    source_filenames.append(filename)
        else:
            logger.debug(u'Considered to be plain chaps without part.')
            chaps = []
            parts = None
            try:
                for filename in map(lambda x: x.strip(), yaml_data['CHAPS']):
                    if not _is_appropriate_re_file(self.source_dir, filename):
                        logger.debug(u'Ignoring {}'.format(filename))
                        continue
                    chaps.append(filename)
                    source_filenames.append(filename)
            except:
                logger.error('Failed to parse CHAPS. Exitting')
                return False

        try:
            if yaml_data.get('POSTDEF'):
                for filename in map(lambda x: x.strip(), yaml_data['POSTDEF']):
                    if not _is_appropriate_file(self.source_dir, filename):
                        logger.debug(u'Ignoring {}'.format(filename))
                        continue
                    postdef_filenames.append(filename)
                    source_filenames.append(filename)
        except:
            logger.waring('Failed to parse POSTDEF. Ignoring..')

        self.predef_filenames = predef_filenames
        self.parts = parts
        self.chaps = chaps
        self.postdef_filenames = postdef_filenames
        self.source_filenames = source_filenames
        self.catalog_file = catalog_file
        self._catalog_files.append(catalog_file)
        return True

    def _recognize_catalog_files(self, logger=None):
        '''
        Scans new and legacy catalog files to detect a project structure.
        New projects with catalog.yml/catalog.yaml will be prioritized.
        '''
        logger = logger or self.logger
        if self._recognize_new_catalog_files(logger=logger):
            return True
        return self._recognize_legacy_catalog_files(logger=logger)

    def _recognize_new_catalog_files(self, logger=None):
        logger = logger or self.logger
        for candidate in ['catalog.yml', 'config.yaml']:
            if self._try_parse_catalog_file(candidate, logger):
                return True

    def _recognize_legacy_catalog_files(self, logger=None):
        '''
        Tries recognizing old catalog files (CHAPS, PREDEF, POSTDEF, PART)
        which has been used before Re:VIEW version 1.3.
        '''
        logger = logger or self.logger
        # First check if at least "CHAPS" file exists or not.
        # If not, abort this procedure immediately.
        chaps_path = _verify_filename(self.source_dir, 'CHAPS', logger)
        if not chaps_path:
            self.logger.error('No valid CHAPS file is available.')
            return False
        self._catalog_files.append('CHAPS')

        catalog_files = []
        predef_filenames = []
        source_filenames = []
        postdef_filenames = []
        source_filenames = []
        parts = None
        chaps = None

        # After checking CHAPS existence, we handle PREDEF before actually
        # looking at CHAPS content, to let the system treat .re files in
        # PREDEF before ones in CHAPS.
        if _is_appropriate_file(self.source_dir, 'PREDEF'):
            catalog_files.append('PREDEF')
            predef_path = os.path.join(self.source_dir, 'PREDEF')
            for line in file(predef_path):
                filename = line.rstrip()
                if not filename:
                    continue
                if not _is_appropriate_file(self.source_dir, filename):
                    logger.debug(u'Ignore {}'.format(filename))
                    continue
                predef_filenames.append(filename)
                source_filenames.append(filename)

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
            parts = []
            current_part = 0
            chaps = None
            part_chaps = []
            for line in file(chaps_path):
                filename = line.rstrip()
                # If empty line appears in CHAPS.
                if not filename:
                    if current_part < len(part_titles):
                        parts.append((part_titles[current_part], part_chaps))
                        current_part += 1
                        part_chaps = []
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
                    part_chaps.append(filename)
                    source_filenames.append(filename)
            parts.append((part_titles[current_part], part_chaps))
        else:
            logger.debug('No valid part information found.')
            parts = None
            chaps = []
            for line in file(chaps_path):
                filename = line.rstrip()
                if not filename:
                    continue
                if not _is_appropriate_re_file(self.source_dir, filename):
                    logger.debug(u'Ignore {}'.format(filename))
                    continue
                chaps.append(filename)
                source_filenames.append(filename)

        if _is_appropriate_file(self.source_dir, 'POSTDEF'):
            catalog_files.append('POSTDEF')
            postdef_path = os.path.join(self.source_dir, 'POSTDEF')
            for line in file(postdef_path):
                filename = line.rstrip()
                if not filename:
                    continue
                if not _is_appropriate_file(self.source_dir, filename):
                    logger.debug(u'Ignore {}'.format(filename))
                    continue
                postdef_filenames.append(filename)
                source_filenames.append(filename)

        self.predef_filenames = predef_filenames
        self.parts = parts
        self.chaps = chaps
        self.postdef_filenames = postdef_filenames
        self.source_filenames = source_filenames
        self.catalog_file = None
        self._catalog_files += catalog_files
        return True
        
    def _detect_parts(self, part_content):
        part_titles = []
        for line in part_content:
            part_titles.append(line.rstrip())
        return part_titles

    def _recognize_draft_files(self):
        logger = self.logger
        for re_file in filter(lambda x: x.endswith('.re'),
                              os.listdir(self.source_dir)):
            if re_file not in self.source_filenames:
                self.draft_filenames.append(re_file)
        return True

    def parse_source_files(self, logger=None):
        '''
        Parses all Re:VIEW files and prepare internal structure.
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
        logger.debug('ReVIEWProject.remove_tempfiles()')
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

    def has_source(self, re_file):
        return re_file in self.all_filenames()

    def get_images_for_source(self, re_file):
        return self.images.get(re_file, [])

    def all_filenames(self):
        '''
        Returns all possible .re files that can be source of output.
        Note draft should come after self.source_filenames.
        '''
        return self.source_filenames + self.draft_filenames

    def _recognize_image_files(self):
        if not os.path.isdir(self.image_dir_path):
            self.logger.debug(u'No image_dir ("{}")'
                              .format(self.image_dir_path))
            return
        parent_filenames = sorted(self.all_filenames())
        image_filenames = sorted(os.listdir(self.image_dir_path))
        i_parents = 0
        i_images = 0
        # Compare two lists from both tops.
        while (i_parents < len(parent_filenames)
               and i_images < len(image_filenames)):
            # e.g. 'chap1.re'
            parent_filename  = parent_filenames[i_parents]
            (parent_id, _) = os.path.splitext(parent_filename)
            # e.g. 'chap1-test1.png', 'chap1/test1.png'
            image_filename = image_filenames[i_images]
            rel_path = '{}/{}'.format(self.image_dir, image_filename)
            abs_path = os.path.normpath('{}/{}'.format(self.image_dir_path,
                                                       image_filename))
            (head, tail) = os.path.splitext(image_filename)
            if os.path.isdir(abs_path):
                # e.g. rel_path ... 'images/chap1/test1.png'
                if parent_id == image_filename:
                    for image_filename2 in os.listdir(abs_path):
                        rel_path2 = '{}/{}'.format(rel_path, image_filename2)
                        pi = ProjectImage(rel_path=rel_path2,
                                          parent_filename=parent_filename,
                                          image_dir=self.image_dir)
                        lst = self.images.setdefault(parent_filename, [])
                        lst.append(pi)
                    i_images += 1
                    i_parents += 1
                elif parent_id < image_filename:
                    self.images.setdefault(parent_filename, [])
                    i_parents += 1
                else:
                    self.unmappable_images.append(image_filename)
                    i_images += 1
            else:
                if head.startswith('{}-'.format(parent_id)):
                    # If the image file starts with the id, it should belong
                    # to the parent.
                    # Create a new object and append it to a list.
                    #
                    # Increment index for the image list only, because
                    # next image file may have same parent.
                    # e.g.
                    # parents: ['chap1.re', 'chap2.re']
                    # images:  ['images/chap1-test1.png',
                    #           'images/chap1-test2.png']
                    pi = ProjectImage(rel_path=rel_path,
                                      parent_filename=parent_filename,
                                      image_dir=self.image_dir)
                    lst = self.images.setdefault(parent_filename, [])
                    lst.append(pi)
                    i_images += 1
                elif parent_id < head:
                    # e.g.
                    # parents: ['chap1.re', 'chap2.re']
                    # images:  ['images/chap2-test1.png',
                    #           'images/chap3-test2.png']
                    self.images.setdefault(parent_filename, [])
                    i_parents += 1
                else:
                    self.unmappable_images.append(image_filename)
                    i_images += 1

    def _get_debug_info(self):
        lst = []
        lst.append(u'config_file: "{}"'.format(self.config_file))
        if self.catalog_file:
            lst.append(u'catalog_file: "{}"'.format(self.catalog_file))
        elif self._catalog_files:
            lst.append(u'catalog_files: {}'.format(self._catalog_files))
        else:
            lst.append(u'No catalog file.')
        lst.append(u'source_filenames(len: {}): {}'
                   .format(len(self.source_filenames), self.source_filenames))
        lst.append(u'predef_filenames(len: {}): {}'
                   .format(len(self.predef_filenames), self.predef_filenames))
        lst.append(u'postdef_filenames(len: {}): {}'
                   .format(len(self.postdef_filenames),
                           self.postdef_filenames))
        if self.parts:
            lst.append(u'parts: {}'.format(self.parts))
        elif self.chaps:
            lst.append(u'chaps: {}'.format(self.chaps))
        else:
            lst.append(u'No parts or chaps')
        return lst

    def _log_debug(self, logger=None):
        logger = logger or self.logger
        for line in self._get_debug_info():
            logger.debug(line)

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


