import os
from setuptools import setup, find_packages

from pyrev import main

README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()

os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(name='pyrev',
      version=main.VERSION,
      packages=find_packages(),
      include_package_data=True,
      license='Apache Software License',
      description='A simple Django app to conduct Web-based polls.',
      long_description=README,
      url='http://mowa-net.jp/',
      author='Daisuke Miyakawa',
      author_email='d.miyakawa@gmail.com',
      entry_points={
        'console_scripts': 'pyrev = pyrev.main:main'
      },
      classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Topic :: Text Processing :: Markup'])
    
