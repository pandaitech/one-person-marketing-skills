from __future__ import annotations

import os

from helpers import StudioTestCase

from studio_core import media


class MediaTest(StudioTestCase):
    def test_probe(self):
        video = self.make_test_video()
        info = media.probe(video)
        self.assertIsNotNone(info["duration"])
        self.assertAlmostEqual(info["duration"], 2.0, delta=0.5)
        self.assertEqual(info["width"], 270)
        self.assertEqual(info["height"], 480)
        self.assertGreater(info["size"], 0)

    def test_poster_generation(self):
        video = self.make_test_video()
        path = media.poster("clip", "c1", 1, video)
        self.assertTrue(os.path.isfile(path))
        self.assertGreater(os.path.getsize(path), 0)
        with open(path, "rb") as f:
            head = f.read(3)
        self.assertEqual(head, b"\xff\xd8\xff")  # jpeg magic

    def test_filmstrip_generation(self):
        video = self.make_test_video()
        path = media.filmstrip("clip", "c1", 1, video)
        self.assertTrue(os.path.isfile(path))
        self.assertGreater(os.path.getsize(path), 0)

    def test_waveform_generation(self):
        video = self.make_test_video()
        path = media.waveform("clip", "c1", 1, video, width=1600, height=96)
        self.assertTrue(os.path.isfile(path))
        with open(path, "rb") as f:
            head = f.read(8)
        self.assertEqual(head, b"\x89PNG\r\n\x1a\n")

    def test_cache_reused_until_source_changes(self):
        video = self.make_test_video()
        path1 = media.poster("clip", "c2", 1, video)
        mtime1 = os.path.getmtime(path1)
        path2 = media.poster("clip", "c2", 1, video)
        self.assertEqual(path1, path2)
        self.assertEqual(os.path.getmtime(path2), mtime1)  # not regenerated

        # touch the source with a new mtime -> cache must be invalidated
        os.utime(video, (os.path.getatime(video) + 5, os.path.getmtime(video) + 5))
        path3 = media.poster("clip", "c2", 1, video)
        self.assertGreaterEqual(os.path.getmtime(path3), mtime1)
