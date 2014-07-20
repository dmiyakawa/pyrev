#!/usr/bin/env python

from pyrev.parser import Parser
import unittest

from logging import getLogger, DEBUG

local_logger = getLogger(__name__)


# from logging import StreamHandler
# handler = StreamHandler()
# handler.setLevel(DEBUG)
# local_logger.setLevel(DEBUG)
# local_logger.addHandler(handler)

from logging import NullHandler
local_logger.addHandler(NullHandler())

def _msg(problems):
    if len(problems) > 1:
        return (u'Multiple problems happned.\n'
                + u'\n'.join(map(lambda problem: str(problem), problems)))
    elif len(problems) == 1:
        return str(problems[0])
    else:
        return u''


class ParserTest(unittest.TestCase):
    def test_parser_basic(self):
        parser = Parser(project=None, logger=local_logger)
        parser._parse_file_inter(['= title', 'world'], 0, 'fake.re')
        self.assertEqual(0, len(parser.reporter.problems),
                         msg=_msg(parser.reporter.problems))

    def test_block_param_bs1(self):
        content = '//footnote[fn][C-\]]'
        parser = Parser(project=None, logger=local_logger)
        parser._parse_file_inter(['= title', content], 0, 'fake.re')
        self.assertEqual(0, len(parser.reporter.problems),
                         msg=_msg(parser.reporter.problems))
        
    def test_block_param_bs2(self):
        content = '//footnote[fn][@<b>{C-\]}]'
        parser = Parser(project=None, logger=local_logger)
        parser._parse_file_inter(['= title', content], 0, 'fake.re')
        self.assertEqual(0, len(parser.reporter.problems),
                         msg=_msg(parser.reporter.problems))
        self.assertEqual(1, len(parser.all_blocks))
        block = parser.all_blocks[0]
        self.assertEqual(2, len(block.params))
        self.assertEqual((u'footnote', 'fn', 2),
                         (block.name, block.params[0], block.line_num))
        self.assertEqual(1, len(parser.all_inlines))
        inline = parser.all_inlines[0]
        # position points to the last char.
        self.assertEqual((u'b', u'C-]', 2, 24),
                         (inline.name, inline.raw_content, inline.line_num,
                          inline.position))

    def test_block_param_bs3(self):
        content = '//footnote[fn][@<b>{C-]}]'
        parser = Parser(project=None, logger=local_logger)
        parser._parse_file_inter(['= title', content], 0, 'fake.re')
        self.assertEqual(1, len(parser.reporter.problems))

        self.assertEqual(1, len(parser.all_blocks))
        block = parser.all_blocks[0]
        self.assertEqual(2, len(block.params))
        self.assertEqual((u'footnote', 'fn', 2),
                         (block.name, block.params[0], block.line_num))
        inline = parser.all_inlines[0]
        # position points to the last char.
        self.assertEqual((u'b', u'C-]', 2),
                         (inline.name, inline.raw_content, inline.line_num))

if __name__ == '__main__':
    unittest.main()
