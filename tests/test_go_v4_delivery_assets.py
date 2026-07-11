from pathlib import Path
import json
import struct
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "go-v4"


class GoV4DeliveryAssetTests(unittest.TestCase):
    qr_cases = {
        "business-card": "https://popmonster.vip/go?src=business-card",
        "package-insert": "https://popmonster.vip/go?src=package-insert",
        "social": "https://popmonster.vip/go?src=social",
    }

    @staticmethod
    def png_size(path: Path) -> tuple[int, int]:
        payload = path.read_bytes()
        if payload[:8] != b"\x89PNG\r\n\x1a\n":
            raise AssertionError(f"not a PNG: {path}")
        return struct.unpack(">II", payload[16:24])

    def test_qr_manifest_and_files_use_fixed_contract(self):
        manifest_path = ASSETS / "qr" / "manifest.json"
        self.assertTrue(manifest_path.is_file())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["qr_version"], 4)
        self.assertEqual(manifest["error_correction"], "Q")
        self.assertEqual(manifest["data_modules"], 33)
        self.assertEqual(manifest["quiet_zone_modules"], 4)
        self.assertEqual(manifest["matrix_modules"], 41)
        self.assertEqual(manifest["png_pixels"], 1640)

        for name, expected_url in self.qr_cases.items():
            with self.subTest(name=name):
                entry = manifest["assets"][name]
                self.assertEqual(entry["url"], expected_url)
                svg = ASSETS / "qr" / entry["svg"]
                png = ASSETS / "qr" / entry["png"]
                self.assertTrue(svg.is_file())
                self.assertTrue(png.is_file())
                root = ET.parse(svg).getroot()
                self.assertEqual(root.attrib["viewBox"], "0 0 41 41")
                self.assertEqual(self.png_size(png), (1640, 1640))

    def test_social_and_print_proofs_have_exact_dimensions(self):
        expected_pngs = {
            "go-qr-story-1080x1920.png": (1080, 1920),
            "go-share-1080x1350.png": (1080, 1350),
            "go-business-card-back-96x60mm-bleed.png": (1134, 709),
            "go-package-insert-106x154mm-bleed.png": (1252, 1819),
        }
        for filename, expected in expected_pngs.items():
            folder = "social" if "1080x" in filename else "print"
            with self.subTest(filename=filename):
                self.assertEqual(self.png_size(ASSETS / folder / filename), expected)

        for filename in (
            "go-business-card-back-90x54mm.pdf",
            "go-package-insert-100x148mm.pdf",
        ):
            with self.subTest(filename=filename):
                payload = (ASSETS / "print" / filename).read_bytes()
                self.assertTrue(payload.startswith(b"%PDF-"))

    def test_artwork_spec_records_physical_release_gates(self):
        spec = (ASSETS / "artwork-spec.md").read_text(encoding="utf-8")
        for value in (
            "22 x 22 mm",
            "42 x 42 mm",
            "90 x 54 mm",
            "100 x 148 mm",
            "3 mm",
            "iOS",
            "Android",
            "business-card",
            "package-insert",
        ):
            with self.subTest(value=value):
                self.assertIn(value, spec)


if __name__ == "__main__":
    unittest.main()
