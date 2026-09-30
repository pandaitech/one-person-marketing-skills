"""Unit tests for the pure parts of scripts/lib/store.py: no network, no real
~/.pandaitech directory (HOME is repointed to a temp dir for the read/write test).
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from lib import store  # noqa: E402


class MergeTests(unittest.TestCase):
    def test_merge_adds_meta_without_touching_unrelated_existing_key(self):
        # "other_app" isn't a platform this skill knows about, but merge must
        # never drop data the credentials file already holds for other keys.
        existing = {"other_app": {"api_key": "unrelated"}}
        merged = store.merge_platform_credentials(existing, "meta", {"page_id": "123"})
        self.assertEqual(merged["other_app"], {"api_key": "unrelated"})
        self.assertEqual(merged["meta"], {"page_id": "123"})
        # original dict must not be mutated
        self.assertNotIn("meta", existing)

    def test_merge_updates_fields_without_wiping_siblings(self):
        existing = {"meta": {"page_id": "123", "fb_ig_token": "old-token"}}
        merged = store.merge_platform_credentials(existing, "meta", {"fb_ig_token": "new-token"})
        self.assertEqual(merged["meta"]["page_id"], "123")
        self.assertEqual(merged["meta"]["fb_ig_token"], "new-token")

    def test_merge_from_empty(self):
        merged = store.merge_platform_credentials({}, "meta", {"page_id": "x"})
        self.assertEqual(merged, {"meta": {"page_id": "x"}})


class ExpiryTests(unittest.TestCase):
    def test_expiry_date_from_now_is_in_the_future(self):
        date_str = store.expiry_date_from_now(7)
        self.assertGreaterEqual(store.days_until(date_str), 6)
        self.assertLessEqual(store.days_until(date_str), 7)

    def test_is_expired_for_past_date(self):
        self.assertTrue(store.is_expired("2000-01-01"))

    def test_is_expired_for_future_date(self):
        future = store.expiry_date_from_now(30)
        self.assertFalse(store.is_expired(future))


class SummaryTests(unittest.TestCase):
    def test_build_summary_all_ok(self):
        checks = [{"name": "Token sah", "ok": True, "hint": None}]
        summary = store.build_summary("meta", checks)
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["platform"], "meta")
        self.assertNotIn("hints", summary)

    def test_build_summary_with_failure_includes_hint_not_value(self):
        checks = [
            {"name": "Token sah", "ok": False, "hint": "Token tak sah."},
            {"name": "Page ID diisi", "ok": True, "hint": None},
        ]
        summary = store.build_summary("meta", checks)
        self.assertEqual(summary["status"], "error")
        self.assertIn("Token tak sah.", summary["hints"])
        # never leak a raw secret-shaped value into the summary
        dumped = json.dumps(summary)
        self.assertNotIn("EAAG", dumped)

    def test_build_summary_never_contains_secret_looking_keys(self):
        checks = [{"name": "Token Facebook + Instagram sah", "ok": True, "hint": None}]
        summary = store.build_summary("meta", checks, expiry="2026-11-01")
        for key in summary:
            self.assertNotIn("token", key.lower().replace("verified", ""))


class ReadWriteTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = self._tmpdir.name

    def tearDown(self):
        if self._old_home is not None:
            os.environ["HOME"] = self._old_home
        else:
            os.environ.pop("HOME", None)
        self._tmpdir.cleanup()

    def test_read_missing_file_returns_empty_dict(self):
        self.assertEqual(store.read_credentials(), {})

    def test_write_then_read_roundtrip_and_permissions(self):
        path = store.write_credentials({"meta": {"page_id": "123"}})
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(store.read_credentials(), {"meta": {"page_id": "123"}})
        if os.name == "posix":
            mode = os.stat(path).st_mode & 0o777
            self.assertEqual(mode, 0o600)

    def test_write_merge_roundtrip(self):
        store.write_credentials({"other_app": {"api_key": "unrelated"}})
        existing = store.read_credentials()
        merged = store.merge_platform_credentials(existing, "meta", {"page_id": "123"})
        store.write_credentials(merged)
        reloaded = store.read_credentials()
        self.assertEqual(reloaded["other_app"]["api_key"], "unrelated")
        self.assertEqual(reloaded["meta"]["page_id"], "123")


class SetupArgparseTests(unittest.TestCase):
    def test_rejects_tiktok_platform_choice(self):
        import setup  # noqa: E402 - imported here so sys.path is already set up

        with self.assertRaises(SystemExit):
            setup.main(["tiktok"])


if __name__ == "__main__":
    unittest.main()
