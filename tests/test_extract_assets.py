import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import tools.extract_assets as extract_assets


class AssetImportTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.image = self.directory / "game.hfs"
        self.image.write_bytes(b"synthetic disk")
        self.output = self.directory / "assets"
        self.forks = {name: name.encode("ascii") for name in extract_assets.RESOURCE_FILES}
        self.forks["Prince of Persia 2"] = b"synthetic application"
        self.profiles = {"schema": 1, "profiles": [{"skill": 0}]}
        audio = patch.object(extract_assets, "extract_audio")
        self.audio = audio.start()
        self.addCleanup(audio.stop)

    def fork(self, _image, name, file_type="rsrc"):
        self.assertEqual(file_type, "APPL" if name == "Prince of Persia 2" else "rsrc")
        return self.forks[name]

    def resource_types(self, data):
        return dict.fromkeys(extract_assets.REQUIRED_RESOURCES[data.decode("ascii")])

    def test_import_creates_all_resources_and_enemy_data_without_saving_the_application(self):
        with (
            patch.object(extract_assets, "get_resource_fork", side_effect=self.fork),
            patch.object(extract_assets, "parse_resource_fork", side_effect=self.resource_types),
            patch.object(extract_assets, "extract_bytes", return_value=self.profiles) as profiles,
        ):
            files = extract_assets.extract_assets(self.image, self.output)
        self.assertEqual(set(files), {*extract_assets.RESOURCE_FILES, "enemy_profiles.json"})
        self.assertEqual({p.name for p in self.output.iterdir()}, set(files))
        for name in extract_assets.RESOURCE_FILES:
            self.assertEqual((self.output / name).read_bytes(), self.forks[name])
        self.assertEqual(json.loads((self.output / "enemy_profiles.json").read_bytes()),
                         self.profiles)
        profiles.assert_called_once_with(self.forks["Prince of Persia 2"],
                                         self.forks["Prince.rsrc"])

    def test_invalid_image_is_rejected_before_creating_output(self):
        self.image.write_bytes(b"not HFS")
        with self.assertRaisesRegex(ValueError, "not a supported Macintosh PoP2"):
            extract_assets.extract_assets(self.image, self.output)
        self.assertFalse(self.output.exists())

    def test_incomplete_resources_do_not_replace_existing_files(self):
        self.output.mkdir()
        old = self.output / "Prince.rsrc"
        old.write_bytes(b"existing game")
        with (
            patch.object(extract_assets, "get_resource_fork", side_effect=self.fork),
            patch.object(extract_assets, "parse_resource_fork", return_value={}),
            self.assertRaisesRegex(ValueError, "missing resources"),
        ):
            extract_assets.extract_assets(self.image, self.output)
        self.assertEqual(old.read_bytes(), b"existing game")
        self.assertEqual(list(self.output.iterdir()), [old])

    def test_unavailable_application_does_not_write_a_partial_installation(self):
        def fork(image, name, kind="rsrc"):
            if kind == "APPL":
                raise FileNotFoundError("Missing application")
            return self.fork(image, name, kind)

        with (
            patch.object(extract_assets, "get_resource_fork", side_effect=fork),
            patch.object(extract_assets, "parse_resource_fork", side_effect=self.resource_types),
            self.assertRaisesRegex(ValueError, "Missing application"),
        ):
            extract_assets.extract_assets(self.image, self.output)
        self.assertFalse(self.output.exists())

    def test_bad_enemy_data_is_reported_as_an_unsupported_image(self):
        with (
            patch.object(extract_assets, "get_resource_fork", side_effect=self.fork),
            patch.object(extract_assets, "parse_resource_fork", side_effect=self.resource_types),
            patch.object(extract_assets, "extract_bytes", side_effect=KeyError("DATA")),
            self.assertRaisesRegex(ValueError, "not a supported Macintosh PoP2"),
        ):
            extract_assets.extract_assets(self.image, self.output)
        self.assertFalse(self.output.exists())

    def test_staging_failure_preserves_the_existing_installation(self):
        self.output.mkdir()
        original = self.output / "Prince.rsrc"
        original.write_bytes(b"existing game")
        with (
            patch.object(extract_assets, "get_resource_fork", side_effect=self.fork),
            patch.object(extract_assets, "parse_resource_fork", side_effect=self.resource_types),
            patch.object(extract_assets, "extract_bytes", return_value=self.profiles),
            patch.object(Path, "write_bytes", side_effect=OSError("Disk full")),
            self.assertRaisesRegex(OSError, "Disk full"),
        ):
            extract_assets.extract_assets(self.image, self.output)
        self.assertEqual(original.read_bytes(), b"existing game")
        self.assertEqual(list(self.output.iterdir()), [original])

    def test_audio_failure_preserves_installed_resources_and_removes_staging(self):
        self.output.mkdir()
        original = self.output / "Prince.rsrc"
        original.write_bytes(b"existing game")
        self.audio.side_effect = ValueError("MIDI rendering failed")
        with (
            patch.object(extract_assets, "get_resource_fork", side_effect=self.fork),
            patch.object(extract_assets, "parse_resource_fork", side_effect=self.resource_types),
            patch.object(extract_assets, "extract_bytes", return_value=self.profiles),
            self.assertRaisesRegex(ValueError, "MIDI rendering failed"),
        ):
            extract_assets.extract_assets(self.image, self.output)
        self.assertEqual(original.read_bytes(), b"existing game")
        self.assertEqual(list(self.output.iterdir()), [original])

    def test_prepared_audio_is_committed_with_the_other_resources(self):
        def audio(_image, _program, _prince, directory, _progress):
            directory.mkdir()
            (directory / "manifest.json").write_bytes(b"{}")
            (directory / "cue-40.wav").write_bytes(b"prepared song")

        self.audio.side_effect = audio
        with (
            patch.object(extract_assets, "get_resource_fork", side_effect=self.fork),
            patch.object(extract_assets, "parse_resource_fork", side_effect=self.resource_types),
            patch.object(extract_assets, "extract_bytes", return_value=self.profiles),
        ):
            files = extract_assets.extract_assets(self.image, self.output)
        self.assertEqual(files["audio/cue-40.wav"], b"prepared song")
        self.assertEqual((self.output / "audio" / "cue-40.wav").read_bytes(), b"prepared song")
        self.assertFalse(list(self.output.glob(".import-*")))


if __name__ == "__main__":
    unittest.main()
