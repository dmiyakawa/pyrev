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

import re
import string

from logging import getLogger, NullHandler
from logging import ERROR, WARNING, INFO, DEBUG

local_logger = getLogger(__name__)
local_logger.addHandler(NullHandler())

# Maximum length is temporary.
r_chap = re.compile(r'^(?P<level>={1,5})(?P<column>[column]?)'
                    r'(?P<sp>\s*)(?P<title>.+)$')
r_end_block = re.compile(r'^//}(?P<junk>.*)$')
r_begin_block = re.compile(r'^(?P<prefix>//)(?P<content>.+)$')
r_manual_warn = re.compile(r'^#@(?P<type>.+)\((?P<message>.+)\)$')


class ParseProblem(Exception):
    def __init__(self, source_name, line_num, uni_line, desc):
        self.source_name = source_name
        self.line_num = line_num
        self.uni_line = uni_line
        self.desc = desc

    def __str__(self):
        if self.line_num:
            line = 'L{}'.format(self.line_num)
        else:
            line = 'L?'
        if self.uni_line:
            content = self.uni_line.rstrip()
        else:
            content = u''
        return repr(u'{} {} {}, {}, content: "{}")'
                    .format(self.source_name,
                            line,
                            self.desc,
                            content))

    @classmethod
    def problem(cls,
                error_level, acceptable_level,
                source_name, line_num, uni_line, desc,
                logger=local_logger):
        '''
        Prepares an Exception (ParseProblem) most relevant
        to a given error_level.

        When the error_level is equal to or more than acceptable_level,
        this function raises it.
        Otherwise, this function returns it.
        '''
        if error_level >= ParseError.LEVEL:
            failure = ParseError(source_name, line_num, uni_line, desc)
        elif error_level >= ParseWarning.LEVEL:
            failure = ParseWarning(source_name, line_num, uni_line, desc)
        elif error_level >= ParseInfo.LEVEL:
            failure = ParseInfo(source_name, line_num, uni_line, desc)
        else:
            failure = ParseDebug(source_name, line_num, uni_line, desc)

        if error_level >= acceptable_level:
            raise failure
        else:
            return failure

    @classmethod
    def error(cls, acceptable_level, source_name, line_num, uni_line, reason,
              logger=local_logger):
        return cls.problem(ERROR, acceptable_level,
                           source_name, line_num, uni_line, reason, logger)

    @classmethod
    def warning(cls, acceptable_level, source_name, line_num, uni_line, reason,
                logger=local_logger):
        return cls.problem(WARNING, acceptable_level,
                           source_name, line_num, uni_line, reason, logger)

    @classmethod
    def info(cls, acceptable_level, source_name, line_num, uni_line, reason,
             logger=local_logger):
        return cls.problem(INFO, acceptable_level, 
                           source_name, line_num, uni_line, reason, logger)

    @classmethod
    def debug(cls, acceptable_level, source_name, line_num, uni_line, reason,
              logger=local_logger):
        return cls.problem(DEBUG, acceptable_level, 
                           source_name, line_num, uni_line, reason, logger)

class ParseError(ParseProblem):
    '''
    Original Re:VIEW tool will mostly causes troubles for that.

    Example:

    //image[image]{

    This will abort Re:VIEW tool itself because it says no to you.
    '''
    LEVEL = ERROR  # 40

class ParseWarning(ParseProblem):
    '''
    Original Re:VIEW tool may or may not handle the case.

    Example:

    //image[image][description]{

    (withuout any actual image for that)

    This will cause no problem with review-compile but will let LaTeX get
    mad at it.
    '''
    LEVEL = WARNING  # 30


class ParseInfo(ParseProblem):
    '''
    It will be parsed gracefully while it may not be good for your own
    project.

    Example:
    A situation where a target file starts without any chap info.
    It will be perfectly ok from the view of syntax, but will cause
    chapter/file mismatch afterwards.
    '''
    LEVEL = INFO  # 20


class ParseDebug(ParseProblem):
    LEVEL = DEBUG  # 10


class Inline(object):
    def __init__(self, name, raw_content, line_num, position=None):
        self.name = name
        self.raw_content = raw_content
        self.line_num = line_num
        self.position = position


class Block(object):
    def __init__(self, name, params, uni_lines, line_num):
        self.name = name
        self.params = tuple(params)
        self.uni_lines = uni_lines
        self.line_num = line_num


class InlineStateMachine(object):
    '''
    State machine for a single inline operation.
    '''

    # e.g. "@<i>{\}}"
    _inline_escape_allowed = set(['}', '\\'])

    # TODO: enum?
    # Nothing is happening.
    ISM_NONE = 'ISM_NONE'
    # "@" appeared.
    # -> ISM_INLINE_TAG | ISM_NONE
    ISM_AT = 'ISM_AT'
    ISM_INLINE_TAG = 'ISM_INLINE_TAG'  # "@<" appeared 
    ISM_END_INLINE_TAG = 'ISM_END_INLINE_TAG'  # "@<...>" appeared
    ISM_INLINE_CONTENT = 'ISM_INLINE_CONTENT' # "@<...>{" appeared
    # "@<...>{..\}}"
    ISM_INLINE_CONTENT_BS = 'ISM_INLINE_CONTENT_BS'
    # "@<...>{..@" appeared, which may be wrong
    ISM_INLINE_CONTENT_AT = 'ISM_INLINE_CONTENT_AT'

    def __init__(self,
                 line_num,
                 uni_line,
                 source_name=None,
                 level=ParseError.LEVEL,
                 logger=local_logger):
        self.line_num = line_num
        self.uni_line = uni_line
        self.logger = logger
        self.source_name = source_name
        self.level = level
        self.problems = []
        self.reset()

    def reset(self):
        '''
        Resets current parsing state.
        '''
        self.unprocessed = []
        self.name = None
        self.state = self.ISM_NONE

    def _error(self, desc):
        self.problems.append(ParseProblem.error(self.level,
                                                self.source_name,
                                                self.line_num,
                                                self.uni_line,
                                                desc,
                                                self.logger))

    def _warning(self, desc):
        self.problems.append(ParseProblem.warning(self.level,
                                                  self.source_name,
                                                  self.line_num,
                                                  self.uni_line,
                                                  desc,
                                                  self.logger))

    def _info(self, desc):
        self.problems.append(ParseProblem.info(self.level,
                                               self.source_name,
                                               self.line_num,
                                               self.uni_line,
                                               desc,
                                               self.logger))

    def parse_ch(self, ch, pos, logger=None):
        '''
        Parses a single character.

        Returns None if this state machine is still parsing the content.
        In that case this object keeps the unresolved data.

        Returns an Inline object if inline parsing is finished.
        Returns a string (unicode) if the content is found to be non-inline,
        so the state machine consideres a caller should handle it.

        A caller must be responsible for returned not-None data since
        this object forgets about them.

        Obviously, this function should look like just returning
        ch as is, unless '@' is given.
        It is definitely an expected behavior.
        '''
        logger = logger or self.logger
        assert type(ch) in [str, unicode] and len(ch) == 1

        ISM_NONE = self.ISM_NONE
        ISM_AT = self.ISM_AT
        ISM_INLINE_TAG = self.ISM_INLINE_TAG
        ISM_END_INLINE_TAG = self.ISM_END_INLINE_TAG
        ISM_INLINE_CONTENT = self.ISM_INLINE_CONTENT
        ISM_INLINE_CONTENT_AT = self.ISM_INLINE_CONTENT_AT
        ISM_INLINE_CONTENT_BS = self.ISM_INLINE_CONTENT_BS

        logger.debug(u' C{} {} {}'.format(pos, self.state, ch))

        # Assertions are used to ensure this implementation has no bug.
        # It is unrelated to ParseProblem.
        if self.state == ISM_NONE:
            if ch == '@':
                self.state = ISM_AT
                return None
            else:
                if self.unprocessed:
                    # This happens (in rare cases).
                    # e.g. If we get "@<tagname>a" and need to tolerate the
                    # apparent error, a should be pushed to self.unprocessed
                    ret = ''.join(self.unprocessed) + ch
                    self.reset()
                    return ret
                else:
                    return ch
        elif self.state == ISM_AT:
            if ch == '<':
                assert len(self.unprocessed) == 0
                self.state = ISM_INLINE_TAG
                return None
            elif ch == '@':
                # Keep the state, dropping the previus '@' character.
                return '@'
            else:
                self.reset()
                return '@' + ch
        elif self.state == ISM_INLINE_TAG:
            if ch == '>':
                assert self.unprocessed is not None
                assert self.name is None
                name = ''.join(self.unprocessed)
                if len(name) == 0:
                    self._error(u'Empty inline name')
                self.name = name
                alnum = string.ascii_letters + string.digits
                all_alnum = reduce(lambda x, y: x and (y in alnum),
                                   self.name, True)
                if not all_alnum:
                    self._error(u'Inline name "{}" has non-alnum'
                                .format(self.name))
                is_upper = lambda y: y in string.ascii_uppercase
                has_uppercase = reduce(lambda x, y: x or (is_upper(y)),
                                       self.name, False)
                if has_uppercase:
                    self._info(u'Inline name "{}" has uppercase'
                               .format(self.name))
                self.unprocessed = []
                self.state = ISM_END_INLINE_TAG
            else:
                self.unprocessed.append(ch)
            return None
        elif self.state == ISM_END_INLINE_TAG:
            if ch == '{':
                self.state = ISM_INLINE_CONTENT
                return None
            else:
                self._error(u'Wrong charactor at C{} ("{{" != "{}")'
                            .format(pos, ch))
                # Because we are sure we saw "@<tagname>", interpret
                # it as "@<tagname>{}" and consume it.
                new_inline = Inline(self.name, '', self.line_num)
                self.reset()
                if ch == '@':
                    self.state = ISM_AT
                else:
                    self.unprocessed.append(ch)
                    self.state = ISM_NONE
                return new_inline
        elif self.state == ISM_INLINE_CONTENT:
            if ch == '}':
                # Finished parsing a single inline. Return it and reset.
                content = ''.join(self.unprocessed)
                new_inline = Inline(self.name, content, self.line_num)
                self.reset()
                return new_inline
            elif ch == '@':
                self.state = ISM_INLINE_CONTENT_AT
                return None
            elif ch == '\\':
                self.state = ISM_INLINE_CONTENT_BS
                return None
            else:
                self.unprocessed.append(ch)
                return None
        elif self.state == ISM_INLINE_CONTENT_AT:
            if ch == '}':
                # Finished parsing a single inline. Return it and reset.
                content = ''.join(self.unprocessed) + '@'
                new_inline = Inline(self.name, content, self.line_num)
                self.reset()
                return new_inline
            elif ch == '<':
                # e.g. "@<tagname>{.. @<"
                # 
                # Currenty we assume "@<" inside inline operation is
                # strange enough to alert.
                #
                # Re:VIEW does not support nested inline op anyway.
                self._info(u'Possible nested inline tag at C{}'.format(pos))

                # Assume those two chars are just normal contents in the
                # surrounding inline operation.
                self.unprocessed.append('@')
                self.unprocessed.append(ch)
                self.state = ISM_INLINE_CONTENT
                return None
            elif ch == '@':
                self.unprocessed.append('@')
                return None
            else:
                self.unprocessed.append('@')
                self.unprocessed.append(ch)
                self.state == ISM_INLINE_CONTENT
                return None
        elif self.state == ISM_INLINE_CONTENT_BS:
            if ch in self._inline_escape_allowed:
                self.unprocessed.append(ch)
                self.state = ISM_INLINE_CONTENT
                return None
            else:
                self._info((u'Backslash inside inline "{}" is'
                            u' not effective toward "{}".')
                           .format(self.name, ch))
                self.unprocessed.append('\\')
                self.unprocessed.append(ch)
                self.state = ISM_INLINE_CONTENT
                return None

        logger.error((u'Unexpected state.'
                      u' line_num: {}, uni_line: {}, pos: {}, state: {}')
                     .format(self.line_num,
                             self.uni_line.rstrip(),
                             pos,
                             self.state))
        raise RuntimeError()


    def end(self):
        '''
        Let the state machine handle the end of content.
        
        Returns remaining unprocessed content as a single string.
        Otherwise return None.
        '''
        ISM_NONE = self.ISM_NONE
        ISM_AT = self.ISM_AT
        ISM_INLINE_TAG = self.ISM_INLINE_TAG
        ISM_END_INLINE_TAG = self.ISM_END_INLINE_TAG
        ISM_INLINE_CONTENT = self.ISM_INLINE_CONTENT
        ISM_INLINE_CONTENT_AT = self.ISM_INLINE_CONTENT_AT
        if self.state == ISM_NONE:
            assert not self.unprocessed 
            return None
        elif self.state == ISM_AT:
            return '@'
        elif self.state in [ISM_INLINE_TAG, ISM_END_INLINE_TAG,
                            ISM_INLINE_CONTENT, ISM_INLINE_CONTENT_AT]:
            self._error(u'Invalid state')
        else:
            raise NotImplementedError()

    @classmethod
    def is_start_inline(cls, ch):
        return ch == '@'

# TODO: Develop MultiLineStateMachine instead.
class BlockStateMachine(object):
    BSM_NONE = 'BSM_NONE'
    BSM_PARSE_NAME = 'BSM_PARSE_NAME'
    BSM_IN_PARAM = 'BSM_IN_PARAM'
    BSM_END_PARAM = 'BSM_END_PARAM'
    BSM_IN_BLOCK = 'BSM_IN_BLOCK'

    def __init__(self,
                 source_name=None,
                 level=ParseError.LEVEL,
                 logger=local_logger):
        self.logger = logger
        self.source_name = source_name
        # Same as "acceptable_level"
        self.level = level
        self.problems = []
        # Inline elements in the block.
        # TODO: make a tree. This should not be isolated from others.
        self.inlines = []
        self.reset()

    def reset(self):
        self.state = self.BSM_NONE
        self.name = None
        self.start_line_num = None
        self.params = []
        self.uni_lines = []

    def _error(self, line_num, uni_line, desc):
        self.problems.append(ParseProblem.error(self.level,
                                                self.source_name,
                                                line_num,
                                                uni_line,
                                                desc,
                                                self.logger))

    def _warning(self, line_num, uni_line, desc):
        self.problems.append(ParseProblem.warning(self.level,
                                                  self.source_name,
                                                  line_num,
                                                  uni_line,
                                                  desc,
                                                  self.logger))

    def _info(self, line_num, uni_line, desc):
        self.problems.append(ParseProblem.info(self.level,
                                               self.source_name,
                                               line_num,
                                               uni_line,
                                               desc,
                                               self.logger))

    def parse_line(self, line_num, uni_line, logger=None):
        '''
        Parses a single line.

        Returns None if this state machine is parsing the line.
        In that case this object keeps the unresolved content.

        Returns a Block object if block parsing is finished.

        Returns a string (unicode) if the content is found to be non-block.
        For the string, it will most likely same as the given "uni_line".
        '''

        logger = logger or self.logger

        BSM_NONE = self.BSM_NONE
        BSM_IN_BLOCK = self.BSM_IN_BLOCK
        assert self.state in [BSM_NONE, BSM_IN_BLOCK]

        rstripped = uni_line.rstrip()
        m_end = r_end_block.match(rstripped)
        m_begin = r_begin_block.match(rstripped)
        if self.state == BSM_NONE:
            if m_end:
                self._error(line_num, uni_line, u'Invalid block end')
            elif m_begin:
                logger.debug(u'Block started at L{}'.format(line_num))
                prefix_len = len(m_begin.group('prefix'))
                content = m_begin.group('content').rstrip()
                # May raise an exception in the function,
                # but in this block we don't care
                ret = self._parse_block_start(line_num, uni_line, content,
                                              prefix_len, logger)
                # BSN_NONE ... //footnote[][]
                # BSN_IN_BLOCK ... //list[][]{
                assert self.state in [BSM_NONE, BSM_IN_BLOCK], self.state

                if ret:
                    assert type(ret) == Block
                    self.reset()
                    return ret

                assert self.name is not None
                self.start_line_num = line_num
                return None
            return uni_line
        elif self.state == BSM_IN_BLOCK:
            if m_end:
                logger.debug(u'Block "{}" ended at L{}'
                             .format(self.name, line_num))
                if m_end.group('junk'):
                    self._error('Junk after block end.')
                # (name, params, raw_content, line_num):
                new_block = Block(name=self.name,
                                  params=self.params,
                                  uni_lines=self.uni_lines,
                                  line_num=self.start_line_num)
                self.reset()
                return new_block
        else:
            raise NotImplementedError()


    def _parse_block_start(self, line_num, uni_line, content, 
                           pos_start, logger=None):
        '''
        Returns Block if the block ends in this line.
        (A typical example for it is footnote block.)
        Return None otherwise, which means we are still in a block.

        For instance, if the following line is available..

        //block[param1][param2]{
        
        .. then this function will handle '[param1][param2]{'
        '''
        logger = logger or self.logger

        BSM_PARSE_NAME = self.BSM_PARSE_NAME
        BSM_IN_PARAM = self.BSM_IN_PARAM
        BSM_END_PARAM = self.BSM_END_PARAM
        BSM_IN_BLOCK = self.BSM_IN_BLOCK

        def __bsm_name_end():
            assert self._tmp_lst is not None
            assert self.name is None, u'name: {}'.format(self.name)
            alnum = string.ascii_letters + string.digits
            name = ''.join(self._tmp_lst)
            self._tmp_lst = []
            if len(name) == 0:
                self._error(line_num, uni_line, u'Empty block name')
            all_alnum = reduce(lambda x, y: x and y in alnum, name, True)
            if not all_alnum:
                reason = u'Block name "{}" contains non-alnum'.format(name)
                self._error(line_num, uni_line, reason)           
            has_uppercase = reduce(lambda x, y:
                                       x or (y in string.ascii_uppercase),
                                   name, False)
            if has_uppercase:
                reason = u'Block name "{}" contains uppercase'.format(name)
                self._info(line_num, uni_line, reason)
            self.name = name

        self._tmp_lst = []
        self._params = []
        self._ism = InlineStateMachine(line_num,
                                       uni_line,
                                       source_name=self.source_name,
                                       level=self.level,
                                       logger=logger)
        self.state = BSM_PARSE_NAME
        for pos, ch in enumerate(content, pos_start):
            logger.debug(u'{} {} {}'.format(pos, self.state, ch))
            if self.state == BSM_PARSE_NAME:
                if ch == '[':
                    __bsm_name_end()
                    self.state = BSM_IN_PARAM
                elif ch == ']':
                    self._error(line_num, uni_line,
                                u'Invalid param end at C{}'.format(pos))
                    self.state = BSM_END_PARAM
                elif ch == '{':
                    # e.g. "//lead{"
                    __bsm_name_end()
                    self.state = BSM_IN_BLOCK
                else:
                    self._tmp_lst.append(ch)
            elif self.state == BSM_IN_PARAM:
                if ch == ']':
                    if self._ism.state != InlineStateMachine.ISM_NONE:
                        self._error(line_num, uni_line,
                                    (u'Inline is not finished'
                                     u' while "]" is found at C{}')
                                    .format(pos))
                    # TODO: Handle ISM_AT state gracefully
                    # (We may want to implement flush() method on ism)
                    new_param = u'{}{}'.format(''.join(self._tmp_lst),
                                               ''.join(self._ism.unprocessed))
                    logger.debug(u'New param "{}"'.format(new_param))
                    self._params.append(new_param)
                    self._ism.reset()
                    self._tmp_lst = []
                    self.state = BSM_END_PARAM
                else:
                    ret = self._ism.parse_ch(ch, pos)
                    if ret is None:
                        # The state machine says inline block is going on.
                        pass
                    elif type(ret) is Inline:
                        self.inlines.append(ret)
                    else:
                        self._tmp_lst.append(ret)
            elif self.state == BSM_END_PARAM:
                if ch == '[':
                    self._ism.reset()
                    self.state = BSM_IN_PARAM
                elif ch == '{':
                    self.state = BSM_IN_BLOCK
                else:
                    self._error(line_num, uni_line,
                                u'Junk at C{}'.format(pos))
            elif self.state == BSM_IN_BLOCK:
                self._error('Junk at C{}'.format(pos))
        self.problems.extend(self._ism.problems)

        if self._ism.state != InlineStateMachine.ISM_NONE:
            self._error(line_num, uni_line, u'Inline is not finished.')
        elif self.state == BSM_PARSE_NAME:
            # e.g. "//noident"
            __bsm_name_end()
            new_block = Block(name=self.name,
                              params=[],
                              uni_lines=[],
                              line_num=line_num)
            self.reset()
            return new_block

        if self._tmp_lst:
            self._error(line_num, uni_line, 
                        'Unprocessed data is remaining ("{}")'
                        .format(''.join(self._tmp_lst)))

        if self.state == BSM_END_PARAM:
            # e.g. "//footnote[fnname][footnotecontent]"
            # name, params, raw_content, line_num):
            new_block = Block(name=self.name,
                              params=self.params,
                              uni_lines=[],
                              line_num=line_num)
            self.reset()
            return new_block

        return None


class Parser(object):
    '''
    Episode 4: A New Hope

    A long time ago, in a galaxy far, far, away...
    '''

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

    def _error(self, line_num, uni_line, desc):
        self.problems.append(ParseProblem.error(self.level,
                                                self.source_name,
                                                line_num,
                                                uni_line,
                                                desc,
                                                self.logger))

    def _warning(self, line_num, uni_line, desc):
        self.problems.append(ParseProblem.warning(self.level,
                                                  self.source_name,
                                                  line_num,
                                                  uni_line,
                                                  desc,
                                                  self.logger))

    def _info(self, line_num, uni_line, desc):
        self.problems.append(ParseProblem.info(self.level,
                                               self.source_name,
                                               line_num,
                                               uni_line,
                                               desc,
                                               self.logger))


    def __init__(self, level=ERROR, logger=local_logger):
        self.logger = logger
        self.level = level

        # TODO:
        # - map list to list
        # - map fn to footnote
        self.allowed_inlines = set([('fn', 1),
                                    ('img', 1),
                                    ('ami', 1),
                                    ('b', 1),
                                    ('i', 1),
                                    ('u', 1),
                                    ('br', 1),
                                    ('list', 1)])
        # Note: table is special. we handle it somewhere else.
        # (name, num_of_params, needs_content)
        self.allowed_blocks = set([('table', 2, True),
                                   ('list', 2, True),
                                   ('emlist', 2, True),
                                   ('image', 2, True),
                                   ('lead', 1, True),
                                   ('footnote', 2, False),
                                   ('noindent', 0, False)])

        self.source_name = None
        self.problems = []

        self.chap_index = None


        # TODO: Merge fragmented information into one..
        self.bsm = None
        self.blocks = []
        self.inlines = []


        # Contains all pointers ("@<fn>{name}", "@<list>{name}")
        # (name, line, pos)
        self.footnote_pointers = []
        self.list_pointers = []

        # A list of bookmarks representing parts/chapters/sections, etc.
        # Each bookmark is actually a plain dict with BM_XXX keys.
        self.bookmarks = []
        # Shortcut to bookmark (only for chapters).
        # key: (source_file, chap_index)
        #
        # value: bookmark
        # chap_index must not be None
        self.chap_to_bookmark = {}


    def parse(self, path, base_level, source_name, logger=None):
        logger = logger or self.logger

        self.source_name = source_name
        self.base_level = base_level
        f = None
        try:
            f = file(path)
            self.bsm = BlockStateMachine(source_name=self.source_name,
                                         level=self.level,
                                         logger=self.logger)
            self.chap_index = 0
            for line_num, line in enumerate(f, 1):
                self._parse_line(line_num, line)
            if self.bsm.state != BlockStateMachine.BSM_NONE:
                self._error(None, None,
                            u'Block "{}" is not ended'.format(self.bsm.name))
        finally:
            if f: f.close()

    def _parse_line(self, line_num, line, logger=None):
        logger = logger or self.logger

        BSM_IN_BLOCK = BlockStateMachine.BSM_IN_BLOCK

        # Kill UTF-8 BOM using 'utf-8-sig'
        uni_line = unicode(line, 'utf-8-sig')
        rstripped = uni_line.rstrip()
        logger.debug(u'_parse_line({}): {}'.format(self.bsm.state, rstripped))

        if self.bsm.state == BSM_IN_BLOCK:
            # Because they are in block, we don't eat their content but include
            # it in the block
            if rstripped[:3] == '#@#':
                self._info(line_num, uni_line,
                           (u'Re:VIEW comment in block "{}".'
                            u' It will be included in the block')
                           .format(self.bsm.name))
            elif rstripped[:2] == '#@':
                m = r_manual_warn.match(rstripped)
                if m:
                    self._warning(line_num, uni_line,
                                  (u'Manual warning in block "{}": "{}".'
                                   u' It will be included in the block')
                                  .format(self.bsm.name, m.group('message')))
            m = r_chap.match(rstripped)
            if m:
                # Treat rare exceptions that may happen in "//list"
                # e.g. "====================================== [1] start
                # e.g. "====================================== [1] end
                if (not m.group('column')
                    and not m.group('sp')
                    and not m.group('title').startswith('=')):
                    self._warning(line_num, uni_line, u'Bookmark in block')
            ret = self.bsm.parse_line(line_num, uni_line)
            if ret is None:
                pass
            elif type(ret) is Block:
                self.blocks.append(ret)
            else:
                pass
        else:
            # "=+" (including column)
            if self._handle_chap(line_num, uni_line):
                pass
            else:
                if rstripped[:3] == '#@#':  # Comment
                    return
                elif rstripped[:2] == '#@':  # warning
                    m = r_manual_warn.match(rstripped)
                    if m:
                        # Only "#@warn(manual-warning)" is allowed.
                        if m.group('type') != 'warn':
                            self._error(line_num, uni_line,
                                        (u'Unknown warn-like operation "{}".'
                                         u' May be "warn". Message: "{}"')
                                        .format(m.group('type'),
                                                m.group('message')))
                        else:
                            self._warning(line_num, uni_line,
                                          (u'Manual warning "{}"'
                                           .format(m.group('message'))))
                        return
                elif rstripped[:1] == '*':
                    self._warning(line_num, uni_line,
                                  (u'Unordered list operator ("*") without'
                                   u' a single space'))
                elif (len(rstripped) > 1
                      and rstripped[0] in string.digits
                      and rstripped[1] == '.'):
                    self._warning(line_num, uni_line,
                                  (u'Ordered list operator ("{}")'
                                   u' without a space')
                                  .format(rstripped[:2]))
        
                if not self.bookmarks:
                    self._info(line_num, uni_line, u'No bookmark found yet')

                ret = self.bsm.parse_line(line_num, uni_line)
                if type(ret) is Block:
                    self.blocks.append(ret)
                    return
                elif ret is None:
                    # bsm eats it.
                    return

                ism = InlineStateMachine(line_num, uni_line,
                                         source_name=self.source_name,
                                         level=self.level,
                                         logger=logger)
                for pos, ch in enumerate(rstripped):
                    ret = ism.parse_ch(ch, pos)
                    if ret is None:
                        pass
                    elif type(ret) is Inline:
                        self.inlines.append(ret)
                    else:
                        pass
                ism.end()
                self.problems.extend(ism.problems)

    def _append_bookmark(self, bookmark, logger=None):
        self.bookmarks.append(bookmark)
        bm_source_file_name = bookmark.get(self.BM_SOURCE_FILE_NAME)
        bm_chap_index = bookmark.get(self.BM_SOURCE_CHAP_INDEX)
        if (bm_source_file_name and bm_chap_index is not None):
            key = (bm_source_file_name, bm_chap_index)
            self.chap_to_bookmark[key] = bookmark

    def _handle_chap(self, line_num, uni_line, logger=None):
        logger = logger or self.logger
        rstripped = uni_line.rstrip()
        m = r_chap.match(rstripped)
        if m:
            level = len(m.group('level'))
            is_column = bool(m.group('column'))
            sp = m.group('sp')
            title = m.group('title')
            if is_column:
                if not self.bookmarks:
                    pass

            if level == 1:
                # If it is a chapter, we set BM_SOURCE_CHAP_INDEX and
                # increment it by one.
                new_bookmark = {self.BM_LEVEL: self.base_level + level,
                                self.BM_TITLE: title.strip(),
                                self.BM_SOURCE_FILE_NAME: self.source_name,
                                self.BM_SOURCE_CHAP_INDEX: self.chap_index,
                                self.BM_SP: sp,
                                self.BM_IS_COLUMN: is_column}
                self.chap_index += 1
            else:
                new_bookmark = {self.BM_LEVEL: self.base_level + level,
                                self.BM_TITLE: title.strip(),
                                self.BM_SOURCE_FILE_NAME: self.source_name,
                                self.BM_SOURCE_CHAP_INDEX: None,
                                self.BM_SP: sp,
                                self.BM_IS_COLUMN: is_column}
            self._append_bookmark(new_bookmark)                
            return True
        else:
            return False

    def _format_bookmark(self, bookmark):
        return ((u'{} "{}"'
                u' (source: {}, index: {})')
                .format('='*bookmark.get(self.BM_LEVEL, 10),
                        bookmark[self.BM_TITLE],
                        bookmark.get(self.BM_SOURCE_FILE_NAME),
                        bookmark.get(self.BM_SOURCE_CHAP_INDEX)))


    def _dump(self, dump_func=None):
        '''
        Dump current state.
        dump_func is expected to accept an arg for each line.
        If there's no dump_func, self.logger.debug() will be used
        '''
        dump_func = dump_func or (lambda x: self.logger.debug(x))
        if self.bookmarks:
            dump_func(u'Bookmarks:')
            for i, bookmark in enumerate(self.bookmarks):
                dump_func(u' {}:{}'.format(i, self._format_bookmark(bookmark)))
        else:
            dump_func(u'No bookmark')
        if self.chap_to_bookmark:
            dump_func(u'chap_to_bookmark:')
            for key in sorted(self.chap_to_bookmark.keys()):
                bookmark = self.chap_to_bookmark[key]
                dump_func(u' {}: "{}"'.format(key, bookmark[self.BM_TITLE]))
        if self.blocks:
            dump_func(u'Blocks:')
            for block in self.blocks:
                dump_func(u' L{} name: "{}", params: {}, lines: {}'
                          .format(block.line_num,
                                  block.name,
                                  block.params,
                                  len(block.uni_lines)))
        else:
            dump_func(u'No block')

        if self.inlines:
            dump_func(u'Inlines:')
            for inline in self.inlines:
                dump_func(u' L{} name: "{}", "{}"'
                          .format(inline.line_num,
                                  inline.name,
                                  inline.raw_content))
        else:
            dump_func(u'No inline')
        if self.problems:
            dump_func(u'Problems:')
            for problem in self.problems:
                name = type(problem).__name__[5]
                if problem.source_name:
                    dump_func(u' [{}] {} L{}: {} (content: "{}")'
                              .format(name,
                                      problem.source_name,
                                      problem.line_num,
                                      problem.desc,
                                      problem.uni_line.rstrip()))
                else:
                    dump_func(u' [{}] L{}: {} (content: "{}")'
                              .format(name,
                                      problem.line_num,
                                      problem.desc,
                                      problem.uni_line.rstrip()))
        else:
            dump_func(u'No problem')

