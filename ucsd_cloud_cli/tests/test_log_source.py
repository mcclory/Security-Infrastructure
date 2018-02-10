from __future__ import absolute_import

import unittest
import json
from click.testing import CliRunner
from ucsd_cloud_cli import cli

class TestLogSource(unittest.TestCase):

    def test_generate_valid_json(self):
        runner = CliRunner()

        result = runner.invoke(cli, ['source', 'generate', '--dry-run'])
        assert result.exit_code == 0
        assert type(json.loads(result.output)) == dict
