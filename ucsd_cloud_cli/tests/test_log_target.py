from __future__ import absolute_import

import unittest
import json
from click.testing import CliRunner
from ucsd_cloud_cli import cli
from .cfn2py import validate_doc

class TestLogTarget(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def test_generate_valid_json(self):
        result = self.runner.invoke(cli, ['target', 'generate', '--dry-run'])
        assert result.exit_code == 0
        assert type(json.loads(result.output)) == dict

    def test_generate_help(self):
        result = self.runner.invoke(cli, ['target', 'generate', '--help'])
        for arg_name in ['-d', '--deploy-account-id', '-n', '--deploy-region-name', '-r', '--region', '-a', '--account', '--dry-run']:
            assert arg_name in result.output

    def test_cfn_structure(self):
        result = self.runner.invoke(cli, ['target', 'generate', '--dry-run'])
        assert validate_doc(result.output)