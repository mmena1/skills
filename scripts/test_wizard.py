#!/usr/bin/env python3
"""Exercise the shared wizard helpers without running its example stages."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = (ROOT / "skills/wizard/template.sh").read_text().split(
    "# STAGES: author this section.", 1
)[0]


class WizardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def run_wizard(self, stages, *, input="", env=None):
        return subprocess.run(
            [shutil.which("bash"), "-c", LIBRARY + "\n" + stages],
            cwd=self.directory, input=input, text=True, capture_output=True,
            env={**os.environ, "ENV_FILE": ".env", **(env or {})}, timeout=10,
        )

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_values_round_trip_and_source_without_execution(self):
        values = ["", "plain", "  spaces # $ ' end  ", "a'b'c", r"back\slash", "one'\\''two",
                  "$(touch executed)`touch executed`'$USER; touch executed"]
        for value in values:
            with self.subTest(value=value):
                result = self.run_wizard('''
write_env TOKEN "$TEST_VALUE"
ask TOKEN "Token:" <<< ''
[[ "$TOKEN" == "$TEST_VALUE" ]]
unset TOKEN
source "$ENV_FILE"
[[ "$TOKEN" == "$TEST_VALUE" ]]
[[ ! -e executed ]]
''', env={"TEST_VALUE": value})
                self.assert_success(result)

    @unittest.skipUnless(os.name == "posix", "requires POSIX links and modes")
    def test_upsert_preserves_symlink_target_mode_and_other_entries(self):
        target = self.directory / "settings.env"
        target.write_text("KEEP=old\nTOKEN=first\nTOKEN=second\n")
        target.chmod(0o640)
        link = self.directory / ".env"
        link.symlink_to(target.name)
        self.assert_success(self.run_wizard('''
write_env TOKEN replacement
source "$ENV_FILE"
[[ "$TOKEN" == replacement && "$KEEP" == old ]]
'''))
        self.assertTrue(link.is_symlink())
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)
        self.assertEqual(target.read_text().count("TOKEN="), 1)
        self.assertIn("KEEP=old\n", target.read_text())

    @unittest.skipUnless(os.name == "posix", "requires POSIX file modes")
    def test_existing_regular_file_keeps_its_mode(self):
        path = self.directory / ".env"
        path.write_text("TOKEN=old\n")
        path.chmod(0o664)
        self.assert_success(self.run_wizard("write_env TOKEN replacement"))
        self.assertEqual(path.stat().st_mode & 0o777, 0o664)

    @unittest.skipUnless(os.name == "posix", "requires POSIX file modes")
    def test_new_file_is_private_even_with_permissive_umask(self):
        self.assert_success(self.run_wizard("umask 000; write_env TOKEN value"))
        self.assertEqual((self.directory / ".env").stat().st_mode & 0o777, 0o600)

    def test_required_prompts_fail_on_eof_even_with_existing_default(self):
        for helper in ("ask", "ask_secret"):
            for saved in (False, True):
                with self.subTest(helper=helper, saved=saved):
                    setup = "write_env TOKEN previous\n" if saved else ""
                    result = self.run_wizard(setup + f'{helper} TOKEN "Token:"\n'
                                             'printf "FLOW_CONTINUED"\n')
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("FLOW_CONTINUED", result.stdout)

    def test_prompts_retain_final_line_and_surrounding_whitespace(self):
        for helper in ("ask", "ask_secret"):
            for newline in ("", "\n"):
                with self.subTest(helper=helper, newline=newline):
                    value = "  literal $ # ' \\  "
                    self.assert_success(self.run_wizard(
                        f'{helper} TOKEN "Token:"\n[[ "$TOKEN" == "$TEST_VALUE" ]]',
                        input=value + newline, env={"TEST_VALUE": value},
                    ))

    def test_secret_default_and_legacy_literal_default_remain_available(self):
        self.assert_success(self.run_wizard('''
write_env TOKEN "a secret '$ with spaces"
ask_secret TOKEN "Token:"
[[ "$TOKEN" == "a secret '$ with spaces" ]]
printf '%s\\n' 'TOKEN=$(touch executed) legacy' > "$ENV_FILE"
ask TOKEN "Token:"
[[ "$TOKEN" == '$(touch executed) legacy' && ! -e executed ]]
''', input="\n\n"))

    def test_legacy_default_keeps_literal_surrounding_single_quotes(self):
        (self.directory / ".env").write_text("TOKEN='literal single quotes'\n")
        self.assert_success(self.run_wizard('''
ask TOKEN 'Keep token:'
[[ "$TOKEN" == "'literal single quotes'" ]]
''', input="\n"))

    def test_missing_or_failing_opener_warns_once_with_url(self):
        for available in (False, True):
            with self.subTest(available=available):
                # Control executable discovery at the operating-system boundary.
                discovery = '''
command() {
  case "$*" in
    '-v wslview'|'-v explorer.exe'|'-v open') return 1 ;;
    '-v xdg-open') AVAILABLE ;;
    *) builtin command "$@" ;;
  esac
}
xdg-open() { return 1; }
'''.replace("AVAILABLE", 'return 0' if available else 'return 1')
                result = self.run_wizard(discovery + '''
open_url 'https://example.test/setup'
printf 'FLOW_CONTINUED'
''')
                self.assert_success(result)
                self.assertEqual(result.stdout.count("visit it manually"), 1)
                self.assertIn("visit it manually: https://example.test/setup", result.stdout)
                self.assertIn("FLOW_CONTINUED", result.stdout)

    def test_successful_stage_flow_keeps_defaults_and_opens_url(self):
        self.assert_success(self.run_wizard('''
command() {
  case "$*" in
    '-v wslview'|'-v explorer.exe') return 1 ;;
    '-v xdg-open') return 0 ;;
    *) builtin command "$@" ;;
  esac
}
xdg-open() { printf '%s' "$1" > opened; }
TOTAL_STAGES=1
banner 'Setup'
stage 'Credentials'
open_url 'https://example.test/setup'
ask TOKEN 'Token:'
ask_secret SECRET 'Secret:'
write_env TOKEN "$TOKEN"
write_env SECRET "$SECRET"
ask TOKEN 'Keep token:'
[[ "$TOKEN" == 'visible value' && "$SECRET" == 'secret value' ]]
[[ "$(cat opened)" == 'https://example.test/setup' ]]
finish
''', input="\nvisible value\nsecret value\n\n"))

    @unittest.skipUnless(hasattr(os, "openpty"), "requires a Unix terminal")
    def test_failed_clear_does_not_stop_stage_on_terminal(self):
        opener, terminal = os.openpty()
        try:
            result = subprocess.run(
                [shutil.which("bash"), "-c", LIBRARY + '''
tput() { return 1; }
stage 'Continue after failed clear'
printf 'FLOW_CONTINUED'
'''], cwd=self.directory, stdin=subprocess.DEVNULL,
                stdout=terminal, stderr=terminal, timeout=10,
            )
            os.set_blocking(opener, False)
            try:
                output = os.read(opener, 8192).decode()
            except BlockingIOError:
                output = ""
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("FLOW_CONTINUED", output)
        finally:
            os.close(opener)
            os.close(terminal)


if __name__ == "__main__":
    unittest.main()
