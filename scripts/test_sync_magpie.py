import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import sync_magpie as sync


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        name = "templates/magpie/redeven-service-template.json"
        self.path = Path(self.directory.name) / name
        self.path.parent.mkdir(parents=True)
        shutil.copyfile(Path(__file__).resolve().parents[1] / name, self.path)
        # Keep version comparisons independent of future updates to the real template.
        self.original = json.loads(self.path.read_bytes())
        self.original.update(recommended_version="0.1.99", revision=7)
        self.digests = {"amd64": "sha256:" + "a" * 64, "arm64": "sha256:" + "b" * 64}
        self.original["platform_artifacts"] = self.artifacts("0.1.99")
        self.source = (json.dumps(self.original, indent=2) + "\n").encode()
        self.path.write_bytes(self.source)
        self.release = {"tag_name": "v0.1.100", "draft": False, "prerelease": False}
        self.index = {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "manifests": [
                {"mediaType": "application/vnd.oci.image.manifest.v1+json",
                 "platform": {"os": "linux", "architecture": arch}, "digest": digest}
                for arch, digest in self.digests.items()
            ] + [{"platform": {"os": "unknown", "architecture": "unknown"}}],
        }

    def artifacts(self, version):
        return {f"linux-{arch}": f"{sync.IMAGE}:{version}@{digest}"
                for arch, digest in self.digests.items()}

    def run_sync(self, arm64_arch="arm64"):
        with patch.object(sync, "inspect_image", side_effect=[
            self.index, {"os": "linux", "architecture": "amd64"},
            {"os": "linux", "architecture": arm64_arch},
        ]) as inspect:
            sync.sync_template(self.path, self.release)
        return inspect

    def test_newer_numeric_version_updates_only_release_fields_and_is_idempotent(self):
        inspect = self.run_sync()
        self.assertEqual([call.args[0] for call in inspect.call_args_list], [
            f"{sync.IMAGE}:0.1.100", f"{sync.IMAGE}@{self.digests['amd64']}",
            f"{sync.IMAGE}@{self.digests['arm64']}",
        ])
        wanted = dict(self.original, revision=8, recommended_version="0.1.100",
                      platform_artifacts=self.artifacts("0.1.100"))
        result = self.path.read_bytes()
        self.assertEqual(json.loads(result), wanted)
        self.run_sync()
        self.assertEqual(self.path.read_bytes(), result)

    def test_older_release_does_not_even_query_the_registry(self):
        self.release["tag_name"] = "v0.1.98"
        self.run_sync().assert_not_called()
        self.assertEqual(self.path.read_bytes(), self.source)

    def test_unsupported_release_never_updates_the_template(self):
        for changes in ({"draft": True}, {"prerelease": True}, {"tag_name": "v0.1.101-rc.1"}):
            with self.subTest(changes=changes), patch.object(sync, "inspect_image") as inspect:
                with self.assertRaises(ValueError):
                    sync.sync_template(self.path, dict(self.release, **changes))
                inspect.assert_not_called()
                self.assertEqual(self.path.read_bytes(), self.source)

    def test_incomplete_or_ambiguous_platform_index_never_updates_the_template(self):
        amd64, arm64, attestation = self.index["manifests"]
        for entries in ([amd64, attestation], [amd64, arm64, arm64]):
            with self.subTest(entries=entries):
                self.index["manifests"] = entries
                with self.assertRaisesRegex(ValueError, "exactly one image for linux-arm64"):
                    self.run_sync()
                self.assertEqual(self.path.read_bytes(), self.source)

    def test_wrong_image_config_never_updates_the_template(self):
        with self.assertRaisesRegex(ValueError, "image config does not match linux-arm64"):
            self.run_sync(arm64_arch="amd64")
        self.assertEqual(self.path.read_bytes(), self.source)

    def test_registry_failure_never_updates_the_template(self):
        with patch.object(sync, "inspect_image", side_effect=subprocess.CalledProcessError(1, "docker")):
            with self.assertRaises(subprocess.CalledProcessError):
                sync.sync_template(self.path, self.release)
        self.assertEqual(self.path.read_bytes(), self.source)

    def test_same_version_digest_drift_requires_manual_review(self):
        self.release["tag_name"] = "v0.1.99"
        self.index["manifests"][0]["digest"] = "sha256:" + "c" * 64
        with self.assertRaisesRegex(ValueError, "manual review required"):
            self.run_sync()
        self.assertEqual(self.path.read_bytes(), self.source)
