#!/usr/bin/env python3
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / "src/floorp-profile-root.sh"


class ProfileRootTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir()
        self.app = self.home / ".var/app/one.ablaze.floorp"
        self.config = self.app / "config"
        self.config.mkdir(parents=True)
        self.legacy = self.app / ".floorp"
        self.xdg = self.config / "floorp"

    def registry(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "profiles.ini").write_text("[General]\nVersion=2\n")

    def select(self, **extra):
        env = {**os.environ, "HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config)}
        env.pop("MOZ_APP_DATA", None)
        env.update(extra)
        return subprocess.run(["bash", "-c", 'source "$1"; floorp_select_profile_root || exit; printf "%s" "$MOZ_APP_DATA"',
                               "test", str(HELPER)], env=env, text=True, capture_output=True)

    def test_new_install_uses_legacy_location(self):
        result = self.select()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout).resolve(), self.legacy)

    def test_legacy_with_or_without_persist_mount(self):
        self.registry(self.legacy)
        self.assertEqual(Path(self.select().stdout).resolve(), self.legacy)
        (self.home / ".floorp").symlink_to(self.legacy, target_is_directory=True)
        self.assertEqual(Path(self.select().stdout).resolve(), self.legacy)

    def test_xdg_only_is_preserved(self):
        self.registry(self.xdg)
        self.assertEqual(Path(self.select().stdout).resolve(), self.xdg)

    def test_host_alias_of_xdg_registry_is_not_a_separate_profile(self):
        self.registry(self.xdg)
        host = self.home / ".floorp"
        host.symlink_to(self.xdg, target_is_directory=True)
        before = (self.xdg / "profiles.ini").read_bytes()
        result = self.select()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout).resolve(), self.xdg)
        self.assertEqual((self.xdg / "profiles.ini").read_bytes(), before)
        self.assertEqual(host.resolve(), self.xdg)
        self.assertFalse(self.legacy.exists())

    def test_host_alias_does_not_hide_conflicting_registries(self):
        self.registry(self.legacy)
        self.registry(self.xdg)
        (self.home / ".floorp").symlink_to(self.xdg, target_is_directory=True)
        before = [(p / "profiles.ini").read_bytes() for p in (self.legacy, self.xdg)]
        result = self.select()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("two Flatpak profile registries", result.stderr)
        self.assertEqual([(p / "profiles.ini").read_bytes() for p in (self.legacy, self.xdg)], before)

    def test_host_registry_file_alias_in_other_directory_is_rejected(self):
        self.registry(self.xdg)
        host = self.home / ".floorp"
        host.mkdir()
        (host / "profiles.ini").hardlink_to(self.xdg / "profiles.ini")
        result = self.select()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("separate host profile", result.stderr)

    def test_host_alias_of_empty_legacy_does_not_override_xdg_registry(self):
        self.registry(self.xdg)
        self.legacy.mkdir()
        (self.home / ".floorp").symlink_to(self.legacy, target_is_directory=True)
        result = self.select()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("separate host profile", result.stderr)
        self.assertFalse((self.legacy / "profiles.ini").exists())

    def mock_mountpoint(self, status):
        # Model mount metadata separately from directory identity. The full
        # Flatpak test also exercises the real --persist bind mount.
        bindir = Path(self.temp.name) / "bin"
        bindir.mkdir()
        command = bindir / "mountpoint"
        command.write_text(f"#!/bin/sh\nexit {status}\n")
        command.chmod(0o755)
        return str(bindir) + os.pathsep + os.environ.get("PATH", "")

    def test_persisted_legacy_mount_allows_selected_xdg_registry(self):
        self.registry(self.xdg)
        host = self.home / ".floorp"
        host.mkdir()
        self.legacy.symlink_to(host, target_is_directory=True)
        result = self.select(PATH=self.mock_mountpoint(0))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout).resolve(), self.xdg)

    def test_legacy_identity_without_mountpoint_is_still_rejected(self):
        self.registry(self.xdg)
        host = self.home / ".floorp"
        host.mkdir()
        self.legacy.symlink_to(host, target_is_directory=True)
        result = self.select(PATH=self.mock_mountpoint(32))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("separate host profile", result.stderr)

    def test_host_symlink_is_not_a_persist_mount_even_if_target_is_mounted(self):
        self.registry(self.xdg)
        self.legacy.mkdir()
        (self.home / ".floorp").symlink_to(self.legacy, target_is_directory=True)
        result = self.select(PATH=self.mock_mountpoint(0))
        self.assertNotEqual(result.returncode, 0)

    def test_mountpoint_alone_does_not_allow_a_separate_host_directory(self):
        self.registry(self.xdg)
        self.legacy.mkdir()
        (self.home / ".floorp").mkdir()
        result = self.select(PATH=self.mock_mountpoint(0))
        self.assertNotEqual(result.returncode, 0)

    def test_both_existing_registries_fail_closed(self):
        self.registry(self.legacy)
        self.registry(self.xdg)
        result = self.select()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("two Flatpak profile registries", result.stderr)
        self.assertTrue((self.legacy / "profiles.ini").exists())
        self.assertTrue((self.xdg / "profiles.ini").exists())

    def test_same_registry_reachable_through_both_paths(self):
        self.registry(self.legacy)
        self.xdg.symlink_to(self.legacy, target_is_directory=True)
        result = self.select()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout).resolve(), self.legacy)

    def test_same_registry_file_in_different_directories_is_ambiguous(self):
        self.registry(self.legacy)
        self.xdg.mkdir()
        (self.xdg / "profiles.ini").hardlink_to(self.legacy / "profiles.ini")
        self.assertNotEqual(self.select().returncode, 0)

    def test_separate_host_directory_fails_closed(self):
        self.registry(self.legacy)
        self.registry(self.home / ".floorp")
        result = self.select()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("separate host profile", result.stderr)

    def test_partial_data_without_registry_fails_closed(self):
        self.legacy.mkdir(parents=True)
        (self.legacy / ".hidden-profile-data").write_text("keep")
        result = self.select()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("without profiles.ini", result.stderr)
        self.assertTrue((self.legacy / ".hidden-profile-data").exists())

    def test_invalid_config_fails_and_explicit_override_is_preserved(self):
        self.assertNotEqual(self.select(XDG_CONFIG_HOME="relative").returncode, 0)
        result = self.select(MOZ_APP_DATA="/custom/profile-root")
        self.assertEqual(result.stdout, "/custom/profile-root")


if __name__ == "__main__":
    unittest.main()
