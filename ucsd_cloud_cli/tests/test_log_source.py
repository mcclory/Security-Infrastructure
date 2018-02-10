from __future__ import absolute_import

import unittest
import json
from click.testing import CliRunner
from ucsd_cloud_cli import cli
from .cfn2py import validate_doc

class TestLogSource(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def test_generate_valid_json(self):
        result = self.runner.invoke(cli, ['source', 'generate', '--dry-run'])
        assert result.exit_code == 0
        assert type(json.loads(result.output)) == dict


    def test_generate_help(self):
        result = self.runner.invoke(cli, ['source', 'generate', '--help'])
        for arg_name in ['--dry-run', '--help']:
            assert arg_name in result.output

    def test_cfn_structure(self):
        result = self.runner.invoke(cli, ['source', 'generate', '--dry-run'])
        assert validate_doc(result.output)
