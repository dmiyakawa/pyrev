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

from project import ReVIEWProject

import os
import shutil


def copy_document(source, dest, logger):
    '''
    Copy a whole document in a single (source) project to another (dest)
    project.
    This also copies relevant images for the document in images/ directory.
    This will not solve dependency between documents.
    Source and dest projects must not be same.

    Returns 0 when successful.

    Note that the dest project may not have same image structure as source
    project. Say we copy src.re to dst.re and src.re has images/src-image.re
    for its image, dst.re may have images/dst/image.re instead of
    images/dst-image.re.

    source: must be a re file under a source project.
    dest: can be a re file (with different name) or a directory.
    '''
    logger.debug(u'Start running copy_chapter "{}" -> "{}"'
                 .format(source, dest))

    if not os.path.exists(source):
        logger.error(u'"{}" does not exist'.format(source))
        return 1
    elif os.path.isdir(source):
        logger.error(u'src file "{}" is not a file.'.format(source))
        return 1

    source_dir = os.path.dirname(os.path.abspath(source))
    source_filename = os.path.basename(source)

    if os.path.isdir(dest):
        if not os.path.exists(dest):
            logger.error(u'"{}" does not exist'.format(dest))
            return 1
        # If destination is a directory, we'll use source name as is.
        dest_filename = source_filename
        dest_dir = os.path.normpath(dest)
    else:
        if os.path.exists(dest):
            logger.error(u'"{}" already exists'.format(dest))
            return 1
        dest_filename = os.path.basename(dest)
        # If the user specifies a filename too, this would contain
        # an extension like ".re"
        if not dest_filename.endswith('.re'):
            logger.error(u'Filename "{}" looks inappropriate. Maybe "{}.re"?'
                         .format(dest_filename, dest_filename))
            return 1
        dest_dir = ReVIEWProject.guess_source_dir(os.path.dirname(dest))

    (dest_parent_id, _) = os.path.splitext(dest_filename)

    logger.debug('source_dir: {}, dest_dir: {}'.format(source_dir, dest_dir))
    if os.path.samefile(source_dir, dest_dir):
        logger.error('src and dst point to a same directory.')
        return 1

    source_project = ReVIEWProject(source_dir, logger=logger)
    dest_project = ReVIEWProject(dest_dir, logger=logger)

    if dest_project.has_source(dest_filename):
        logger.error('{} already exists on dest side.'
                     .format(source_filename))
        return 1

    source_path = os.path.join(os.path.abspath(source_project.source_dir),
                               source_filename)
    dest_path = os.path.join(os.path.abspath(dest_project.source_dir),
                             dest_filename)
    
    if os.path.exists(dest_project.image_dir_path):
        if not os.path.isdir(dest_project.image_dir_path):
            logger.error('{} is not a directory.'
                         .format(dest_project.image_dir_path))
            return 1
    else:
        dest_image_dir_path = dest_project.image_dir_path
        logger.debug('Creating a directory "{}" as an image_dir'
                     .format(dest_image_dir_path))
        try:
            os.mkdir(dest_image_dir_path)
        except OSError as e:
            logger.error('Failed to create "{}": {}'
                         .format(dest_image_dir_path, e))
            return 1

    source_images = source_project.get_images_for_source(source_filename)
    if source_images:
        # For destination, use 'images/project/image.png' format
        # instead of "images/project-image.png" format,
        # regardless of source's status.
        #
        # e.g.
        # If we are copying src.re to dst.re and source has
        # an image file 'images/src-image1.png', it will be copied to
        # 'images/dst/image1.png' on dest side.
        # 'images/dst-image1.png' will NOT be available.
        sub_image_dir = os.path.join(dest_project.image_dir_path,
                                     dest_parent_id)
        if not os.path.exists(sub_image_dir):
            logger.debug('Creating a directory "{}" for a sub image_dir'
                         .format(sub_image_dir))
            try:
                os.mkdir(sub_image_dir)
            except OSError as e:
                logger.error('Failed to create "{}": {}'
                             .format(sub_image_dir, e))
                return 1
        for image in source_images:
            src_image_path = os.path.join(source_project.source_dir,
                                          image.rel_path)
            dest_image_path = os.path.join(sub_image_dir,
                                           '{}{}'.format(image.id, image.tail))
            logger.debug('Copying from "{}" to "{}".'
                         .format(src_image_path, dest_image_path))
            shutil.copyfile(src_image_path, dest_image_path)

    logger.debug('Copying from "{}" to "{}"'.format(source_path, dest_path))
    shutil.copyfile(source_path, dest_path)
    return 0
