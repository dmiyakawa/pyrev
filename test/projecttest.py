#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
_cur_dir = os.path.dirname(os.path.realpath(__file__))
_parent_dir = os.path.dirname(_cur_dir)
_projects_dir = os.path.join(_cur_dir, 'projects')
import sys
sys.path.insert(0, _parent_dir)

from pyrev.project import ReVIEWProject
import unittest

from testutil import setup_logger

_debug = False
local_logger = setup_logger(__name__, _debug)

class ProjectTest(unittest.TestCase):
    def test_check_draft(self):
        source_dir = os.path.join(_projects_dir, 'project1')
        project = ReVIEWProject(source_dir, logger=local_logger)
        self.assertEqual(1, len(project.source_filenames))
        self.assertTrue('project1.re' in project.source_filenames)
        self.assertEqual(1, len(project.draft_filenames))
        self.assertTrue('draft1.re' in project.draft_filenames)
        self.assertTrue(project.images.has_key('project1.re'))
        self.assertEqual(1, len(project.images['project1.re']))
        img1 = project.images['project1.re'][0]
        self.assertEqual('images/project1-mowadeco.png', img1.rel_path)
        self.assertEqual('project1.re', img1.parent_filename)
        self.assertEqual('project1', img1.parent_id)
        self.assertEqual('mowadeco', img1.id)

        self.assertTrue(project.images.has_key('draft1.re'))
        self.assertEqual(1, len(project.images['draft1.re']))
        img2 = project.images['draft1.re'][0]
        self.assertEqual('images/draft1/mowa.jpg', img2.rel_path)
        self.assertEqual('draft1.re', img2.parent_filename)
        self.assertEqual('draft1', img2.parent_id)
        self.assertEqual('mowa', img2.id)



if __name__ == '__main__':

    unittest.main()
