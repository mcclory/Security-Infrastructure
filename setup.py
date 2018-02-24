import sys
from setuptools import setup, find_packages
import pip

from pip.req import parse_requirements

from ucsd_cloud_cli import VERSION

NAME = "ucsd_cloud_cli"

# To install the library, run the following
#
# python setup.py install
#
# prerequisite: setuptools
# http://pypi.python.org/pypi/setuptools

parsed_requirements = parse_requirements(
    'requirements/prod.txt',
    session=pip.download.PipSession()
)

parsed_test_requirements = parse_requirements(
    'requirements/test.txt',
    session=pip.download.PipSession()
)

requirements = [str(ir.req) for ir in parsed_requirements]
test_requirements = [str(tr.req) for tr in parsed_test_requirements]

setup(
    name=NAME,
    version=VERSION,
    description="UCSD Cloud CLI Wrapper",
    author_email="dev@introspectdata.com",
    url="https://github.com/IntrospectData/ucsd-cloud-cli",
    keywords=["Click", "UCSD Cloud CLI"],
    install_requires=requirements,
    packages=find_packages(),
    package_data={'': ['data/cloudformation/*']},
    include_package_data=True,
    license="Private",
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: Other/Proprietary License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6'
    ],
    entry_points='''
        [console_scripts]
        ucsd_cloud_cli=ucsd_cloud_cli.__main__:main
        ccli=ucsd_cloud_cli.__main__:main
    ''',
    tests_require=test_requirements
)
