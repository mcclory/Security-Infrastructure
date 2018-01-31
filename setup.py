from setuptools import setup

setup(
    name='ucsd_cloud_cli',
    version='0.1.0',
    py_modules=['ucsd_cloud_cli'],
    install_requires=[
        'Click',
        'boto3'
    ],
    entry_points='''
        [console_scripts]
        ccli=ucsd_cloud_cli:__main__
    ''',
)
