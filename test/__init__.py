#!/usr/bin/env python

import unittest

import os
_cur_dir = os.path.dirname(os.path.realpath(__file__))
_parent_dir = os.path.dirname(_cur_dir)
import sys
sys.path.insert(0, _parent_dir)

from regtest import RegressionTest
from parsertest import ParserTest
from projecttest import ProjectTest

if __name__ == '__main__':

    unittest.main()
