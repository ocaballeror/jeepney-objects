"""
Setup module.
"""
from glob import glob
from os.path import splitext, basename
from setuptools import setup, find_packages

setup(
    name='jeepney_objects',
    version='v0.1.0',
    description='Publish and manage pure python DBus objects',
    url='https://github.com/ocaballeror/jeepney-objects',
    author='Oscar Caballero',
    author_email='ocaballeror@tutanota.com',
    license='GNU General Public License, Version 3',
    classifiers=[
        'Environment :: Console',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
    packages=find_packages('src'),
    package_dir={'': 'src'},
    py_modules=[splitext(basename(path))[0] for path in glob('src/*.py')],
    python_requires='>=3.5',
    install_requires=['jeepney'],
)
