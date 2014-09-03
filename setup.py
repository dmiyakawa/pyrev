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
from setuptools import setup, find_packages

from pyrev import main

README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()

# os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(name='pyrev',
      version=main.VERSION,
      author='Daisuke Miyakawa',
      author_email='d.miyakawa@gmail.com',
      description='Another Re:VIEW (lint) tool',
      long_description=README,
      packages=find_packages(),
      package_data={'pyrev': ['README.rst']},
      include_package_data=True,
      license='Apache License 2.0',
      entry_points={
        'console_scripts': ['pyrev = pyrev.main:main',
                            'pyrev-devel = pyrev.devel:devel']
      },
      url='https://github.com/dmiyakawa/pyrev',
      classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Topic :: Text Processing :: Markup'])
    
