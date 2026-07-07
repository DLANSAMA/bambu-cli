from tests.bambu_test_base import *  # noqa: F401,F403


class TestLoadConfig(unittest.TestCase):


    @patch('bambu_cli.bambu.subprocess.run')
    @patch('bambu_cli.bambu.logger')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    def test_cmd_slice_convert_step_to_stl_argument_injection(self, mock_getsize, mock_exists, mock_logger, mock_run):
        from bambu_cli.bambu import _convert_step_to_stl
        import os

        # Setup mocks
        mock_run.return_value.returncode = 0
        mock_exists.return_value = True
        mock_getsize.return_value = 1024

        filepath = "-malicious.step"
        abs_filepath = os.path.abspath(filepath)
        expected_stl_path = abs_filepath.rsplit('.', 1)[0] + '.stl'

        res_filepath, success = _convert_step_to_stl(filepath)

        self.assertTrue(success)
        self.assertTrue(res_filepath.endswith("-malicious_.stl"))
        self.assertIn("bambu_step_", res_filepath)

        # Verify that subprocess.run was called with absolute paths
        self.assertEqual(mock_run.call_count, 1)
        args_run, kwargs_run = mock_run.call_args
        cmd_run = args_run[0]
        self.assertIn("gmsh", cmd_run)
        self.assertIn(abs_filepath, cmd_run)
        self.assertIn("-o", cmd_run)
        out_idx = cmd_run.index("-o") + 1
        self.assertTrue(cmd_run[out_idx].endswith("-malicious_.stl"))
        self.assertIn("bambu_step_", cmd_run[out_idx])
        self.assertEqual(kwargs_run, {'capture_output': True, 'text': True, 'timeout': 60})

    @patch('os.path.exists')
    @patch('bambu_cli.bambu.logger')
    @patch('sys.exit')
    def test_load_config_not_found(self, mock_exit, mock_logger, mock_exists):
        mock_exists.return_value = False
        mock_exit.side_effect = SystemExit(1)

        with self.assertRaises(SystemExit) as cm:
            load_config()

        self.assertEqual(cm.exception.code, 1)
        mock_exit.assert_called_once_with(1)
        # Check if instructions were logged
        self.assertTrue(any("Config not found" in call[0][0] for call in mock_logger.error.call_args_list))

    @patch('os.stat')
    @patch('os.path.exists')
    @patch('bambu_cli.bambu.logger')
    @patch('sys.exit')
    @patch('builtins.open', new_callable=mock_open, read_data='invalid json')
    def test_load_config_invalid_json(self, mock_file, mock_exit, mock_logger, mock_exists, mock_stat):
        mock_exists.return_value = True
        mock_exit.side_effect = SystemExit(1)

        with self.assertRaises(SystemExit) as cm:
            load_config()

        self.assertEqual(cm.exception.code, 1)
        self.assertTrue(any("Error loading config" in call[0][0] for call in mock_logger.error.call_args_list))



    @patch('os.path.exists')
    def test_load_config_not_found_no_exit(self, mock_exists):
        from bambu_cli.bambu import load_config
        mock_exists.return_value = False
        result = load_config(exit_on_fail=False)
        self.assertIsNone(result)

    @patch('os.stat')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='invalid json')
    def test_load_config_invalid_json_no_exit(self, mock_file, mock_exists, mock_stat):
        from bambu_cli.bambu import load_config
        mock_exists.return_value = True
        result = load_config(exit_on_fail=False)
        self.assertIsNone(result)


class TestLoadAccessCode(unittest.TestCase):

    @patch('bambu_cli.bambu._cfg', {'access_code': 'inline_secret'})
    def test_load_access_code_inline(self):
        from bambu_cli.bambu import load_access_code
        if hasattr(load_access_code, 'cache_clear'):
            load_access_code.cache_clear()
        import bambu_cli.bambu
        with patch.dict(bambu_cli.bambu._cfg, {'access_code': 'inline_secret'}, clear=True):
            self.assertEqual(bambu_cli.bambu.load_access_code(), 'inline_secret')

    @patch('os.path.expanduser')
    @patch('builtins.open', new_callable=mock_open, read_data=' file_secret ')
    def test_load_access_code_file(self, mock_file, mock_expanduser):
        from bambu_cli.bambu import load_access_code
        if hasattr(load_access_code, 'cache_clear'):
            load_access_code.cache_clear()
        import bambu_cli.bambu
        with patch.dict(bambu_cli.bambu._cfg, {'access_code_file': '~/.config/bambu/secret'}, clear=True):
            mock_expanduser.return_value = '/home/user/.config/bambu/secret'
            self.assertEqual(bambu_cli.bambu.load_access_code(), 'file_secret')

    @patch('bambu_cli.bambu.logger')
    @patch('sys.exit')
    @patch('os.path.expanduser')
    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_load_access_code_file_not_found(self, mock_file, mock_expanduser, mock_exit, mock_logger):
        from bambu_cli.bambu import load_access_code
        if hasattr(load_access_code, 'cache_clear'):
            load_access_code.cache_clear()
        import bambu_cli.bambu
        with patch.dict(bambu_cli.bambu._cfg, {'access_code_file': '~/.config/bambu/missing'}, clear=True):
            mock_exit.side_effect = SystemExit(1)
            with self.assertRaises(SystemExit) as cm:
                bambu_cli.bambu.load_access_code()
            self.assertEqual(cm.exception.code, 1)
            self.assertTrue(any("Access code file not found" in call[0][0] for call in mock_logger.error.call_args_list))

    @patch('bambu_cli.bambu.logger')
    @patch('sys.exit')
    def test_load_access_code_missing(self, mock_exit, mock_logger):
        from bambu_cli.bambu import load_access_code
        if hasattr(load_access_code, 'cache_clear'):
            load_access_code.cache_clear()
        import bambu_cli.bambu
        with patch.dict(bambu_cli.bambu._cfg, {}, clear=True):
            mock_exit.side_effect = SystemExit(1)
            with self.assertRaises(SystemExit) as cm:
                bambu_cli.bambu.load_access_code()
            self.assertEqual(cm.exception.code, 1)
            mock_logger.error.assert_called_with("No 'access_code' or 'access_code_file' in config.json")


class TestSetupLogging(unittest.TestCase):
    @patch('bambu_cli.cli.logging')
    @patch('bambu_cli.cli.sys')
    def test_setup_logging_default(self, mock_sys, mock_logging):
        import bambu_cli.cli as bambu_cli_module

        mock_root = MagicMock()
        mock_handler = MagicMock()
        mock_root.handlers = [mock_handler]

        def get_logger_side_effect(name=None):
            if name is None or name == "bambu_cli":
                return mock_root
            return MagicMock()

        mock_logging.getLogger.side_effect = get_logger_side_effect

        with patch.dict('sys.modules', {'rich': None, 'rich.logging': None, 'rich.console': None, 'rich.traceback': None}):
            with patch('bambu_cli.cli.logger') as mock_logger:
                bambu_cli_module.setup_logging()

                # Check root handler removal
                mock_root.removeHandler.assert_called_once_with(mock_handler)

                # Check StreamHandler and Formatter are created
                mock_logging.StreamHandler.assert_called_once_with(mock_sys.stderr)
                mock_logging.Formatter.assert_called_once_with('%(levelname)s: %(message)s')

                # Check log level setting
                mock_logger.setLevel.assert_called_once_with(mock_logging.INFO)

                # Check propagate False
                self.assertFalse(mock_logger.propagate)

    @patch('bambu_cli.cli.logging')
    @patch('bambu_cli.cli.sys')
    def test_setup_logging_verbose(self, mock_sys, mock_logging):
        import bambu_cli.cli as bambu_cli_module

        mock_root = MagicMock()

        def get_logger_side_effect(name=None):
            if name is None or name == "bambu_cli":
                return mock_root
            return MagicMock()

        mock_logging.getLogger.side_effect = get_logger_side_effect

        with patch.dict('sys.modules', {'rich': None, 'rich.logging': None, 'rich.console': None, 'rich.traceback': None}):
            with patch('bambu_cli.cli.logger') as mock_logger:
                bambu_cli_module.setup_logging(verbose=True)
                mock_logger.setLevel.assert_called_once_with(mock_logging.DEBUG)
                self.assertFalse(mock_logger.propagate)


if __name__ == '__main__':
    unittest.main()
