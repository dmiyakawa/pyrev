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
sys.path.insert(0, parent_dir)

from pyrev.parser import Parser
from pyrev.project import ReVIEWProject
from pyrev import utils

import unittest

import shutil
import tempfile
from testutil import setup_logger

_debug = False
local_logger = setup_logger(__name__, _debug)

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

    def test_copy_document1(self):
        tempdir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(projects_dir, 'project1')
            dest_dir = os.path.join(tempdir, 'project2')
            source = os.path.join(source_dir, 'project1.re')
            dest = dest_dir  
            shutil.copytree(os.path.join(projects_dir, 'project2'),
                            dest_dir)
            dest_project = ReVIEWProject(dest_dir, logger=local_logger)
            self.assertEqual(1, len(dest_project.all_filenames()))
            self.assertEqual(0, len(dest_project
                                    .get_images_for_source('project1.re')))
            self.assertEqual(0, utils.copy_document(source, dest,
                                                    local_logger))
            dest_project = ReVIEWProject(dest_dir, logger=local_logger)
            self.assertEqual(2, len(dest_project.all_filenames()))
            images = dest_project.get_images_for_source('project1.re')
            self.assertEqual(1, len(images))
        finally:
            shutil.rmtree(tempdir)

    def test_copy_document2(self):
        tempdir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(projects_dir, 'project1')
            dest_dir = os.path.join(tempdir, 'project2')
            source = os.path.join(source_dir, 'project1.re')
            dest = os.path.join(dest_dir, 'projectX.re')
            shutil.copytree(os.path.join(projects_dir, 'project2'),
                            dest_dir)
            dest_project = ReVIEWProject(dest_dir, logger=local_logger)
            self.assertEqual(1, len(dest_project.all_filenames()))
            self.assertEqual(0, len(dest_project
                                    .get_images_for_source('project1.re')))
            self.assertEqual(0, utils.copy_document(source, dest,
                                                    local_logger))
            dest_project = ReVIEWProject(dest_dir, logger=local_logger)
            self.assertEqual(2, len(dest_project.all_filenames()))
            images = dest_project.get_images_for_source('projectX.re')
            self.assertEqual(1, len(images))
            image = images[0]
            self.assertEqual('images/projectX/mowadeco.png', image.rel_path)
        finally:
            shutil.rmtree(tempdir)

    def test_move_document1(self):
        tempdir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(tempdir, 'project1')
            dest_dir = os.path.join(tempdir, 'project2')
            shutil.copytree(os.path.join(projects_dir, 'project1'), source_dir)
            shutil.copytree(os.path.join(projects_dir, 'project2'), dest_dir)
            source = os.path.join(source_dir, 'project1.re')
            dest = os.path.join(dest_dir, 'projectX.re')
            source_project = ReVIEWProject(source_dir, logger=local_logger)
            self.assertEqual(2, len(source_project.all_filenames()))
            self.assertTrue('project1.re' in source_project.all_filenames())

            dest_project = ReVIEWProject(dest_dir, logger=local_logger)
            self.assertEqual(1, len(dest_project.all_filenames()))
            self.assertEqual(0, len(dest_project
                                    .get_images_for_source('project1.re')))
            self.assertEqual(0, utils.move_document(source, dest,
                                                    local_logger))
            source_project = ReVIEWProject(source_dir, logger=local_logger)
            self.assertEqual(1, len(dest_project.all_filenames()))
            self.assertTrue('project1.re' not in dest_project.all_filenames())

            dest_project = ReVIEWProject(dest_dir, logger=local_logger)
            self.assertEqual(2, len(dest_project.all_filenames()))
            images = dest_project.get_images_for_source('projectX.re')
            self.assertEqual(1, len(images))
            image = images[0]
            self.assertEqual('images/projectX/mowadeco.png', image.rel_path)
        finally:
            shutil.rmtree(tempdir)

    def test_move_document2(self):
        tempdir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(tempdir, 'project1')
            shutil.copytree(os.path.join(projects_dir, 'project1'), source_dir)

            source = os.path.join(source_dir, 'project1.re')
            dest = os.path.join(source_dir, 'projectX.re')
            source_project = ReVIEWProject(source_dir, logger=local_logger)
            self.assertEqual(2, len(source_project.all_filenames()))
            self.assertTrue('project1.re' in source_project.all_filenames())
            self.assertTrue('projectX.re' not in source_project.all_filenames())
            self.assertEqual(0, utils.move_document(source, dest, local_logger))

            source_project = ReVIEWProject(source_dir, logger=local_logger)
            local_logger.debug('HELLO')
            source_project._log_debug(logger=local_logger)
            # Note that both become draft files because catalog.yml won't
            # track this action.
            self.assertEqual(2, len(source_project.all_filenames()))
            self.assertTrue('project1.re' not in source_project.all_filenames())
            self.assertTrue('projectX.re' in source_project.all_filenames())
            images = source_project.get_images_for_source('projectX.re')
            self.assertEqual(1, len(images))
            image = images[0]
            self.assertEqual('images/projectX/mowadeco.png', image.rel_path)
        finally:
            shutil.rmtree(tempdir)


if __name__ == '__main__':
    unittest.main()
