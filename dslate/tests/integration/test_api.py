from .conftest import run_cli

class TestBasicCLI:
    def test_help(self, cli_exe):
        result = run_cli(cli_exe, ["--help"])
        assert result.returncode == 0
        assert "dslate" in result.stdout
        assert "Usage" in result.stdout

    def test_version(self, cli_exe):
        result = run_cli(cli_exe, ["--version"])
        assert result.returncode == 0
        # Version format might vary, but should contain version info
        assert result.stdout.strip()
