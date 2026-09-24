from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import ch4os_capture as capture


PACK = b'''name = "Example"
pack-format = "packwiz:1.1.0"
[index]
file = "index.toml"
hash-format = "sha256"
hash = "abc"
[versions]
minecraft = "1.21.1"
neoforge = "21.1.248"
'''


class PackSourceTests(unittest.TestCase):
    def test_direct_link(self):
        url = "https://example.test/pack.toml"
        with tempfile.TemporaryDirectory() as temporary, patch.object(capture, "read_pack_url", return_value=PACK):
            info, resolved, root = capture.resolve_source(url, Path(temporary))
        self.assertEqual(info["neoforge"], "21.1.248")
        self.assertEqual(resolved, url)
        self.assertIsNone(root)

    def test_github_file_link_is_normalized_to_packwiz_raw_url(self):
        link = "https://github.com/example/pack/blob/public/pack/pack.toml"
        raw = "https://raw.githubusercontent.com/example/pack/public/pack/pack.toml"
        with tempfile.TemporaryDirectory() as temporary, patch.object(capture, "read_pack_url", return_value=PACK) as reader:
            _, resolved, _ = capture.resolve_source(link, Path(temporary))
        self.assertEqual(resolved, raw)
        reader.assert_called_once_with(raw)

    def test_prism_zip_uses_url_without_running_embedded_jar(self):
        url = "https://example.test/pack.toml"
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "prism.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("Instance/instance.cfg", f'PreLaunchCommand="$INST_JAVA" -jar packwiz-installer.jar -s client "{url}"\n')
                output.writestr("Instance/.minecraft/packwiz-installer.jar", b"untrusted jar")
            with patch.object(capture, "read_pack_url", return_value=PACK):
                info, resolved, root = capture.resolve_source(str(archive), Path(temporary))
            self.assertEqual(info["minecraft"], "1.21.1")
            self.assertEqual(resolved, url)
            self.assertIsNone(root)

    def test_bundled_pack_is_served_from_zip(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            archive = folder / "pack.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("Example/pack.toml", PACK)
                output.writestr("Example/index.toml", b"files = []\n")
            info, url, root = capture.resolve_source(str(archive), folder)
            self.assertEqual(info["name"], "Example")
            self.assertIsNone(url)
            with capture.serve_pack(root) as local_url:
                from urllib.request import urlopen
                self.assertEqual(urlopen(local_url).read(), PACK)
                self.assertEqual(urlopen(local_url.replace("pack.toml", "index.toml")).read(), b"files = []\n")

    def test_unsafe_bundled_zip_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            archive = folder / "pack.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("pack.toml", PACK)
                output.writestr("../outside.txt", "bad")
            with self.assertRaises(capture.CaptureError):
                capture.resolve_source(str(archive), folder)

    def test_other_minecraft_family_reports_incompatibility(self):
        with self.assertRaisesRegex(capture.CaptureError, "supports Minecraft 1.21.1"):
            capture.parse_pack(PACK.replace(b"1.21.1", b"1.21.4"))


if __name__ == "__main__":
    unittest.main()
