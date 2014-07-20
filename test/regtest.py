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

import os
cur_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.dirname(cur_dir)
projects_dir = os.path.join(cur_dir, 'projects')
import sys
sys.path.append(parent_dir)

from pyrev.parser import Parser
from pyrev.project import ReVIEWProject
import unittest

from logging import getLogger, DEBUG

local_logger = getLogger(__name__)
_debug = False

if _debug:
    from logging import StreamHandler
    handler = StreamHandler()
    handler.setLevel(DEBUG)
    local_logger.setLevel(DEBUG)
    local_logger.addHandler(handler)
else:
    from logging import NullHandler
    local_logger.addHandler(NullHandler())

class RegressionTest(unittest.TestCase):
    def _test_no_problem(self, project_name):
        source_dir = os.path.join(projects_dir, project_name)
        project = ReVIEWProject(source_dir, logger=local_logger)
        parser = Parser(project=project, logger=local_logger)
        self.assertEqual(0, len(parser.reporter.problems))
        return (project, parser)

    def test_project1(self):
        self._test_no_problem('project1')

    def test_listnum(self):
        self._test_no_problem('listnum')


if __name__ == '__main__':
    unittest.main()
