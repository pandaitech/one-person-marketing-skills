"""Shared test scaffolding: an isolated STUDIO_DATA_DIR per test + a tiny
generated test video."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if STUDIO_DIR not in sys.path:
    sys.path.insert(0, STUDIO_DIR)


class StudioTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="studio-test-")
        self._old_env = os.environ.get("STUDIO_DATA_DIR")
        os.environ["STUDIO_DATA_DIR"] = self._tmp
        # media.py caches ffmpeg-generation locks by path; nothing to reset
        # since each test uses a fresh cache dir under the temp data dir.

    def tearDown(self):
        if self._old_env is None:
            os.environ.pop("STUDIO_DATA_DIR", None)
        else:
            os.environ["STUDIO_DATA_DIR"] = self._old_env
        shutil.rmtree(self._tmp, ignore_errors=True)

    def make_test_video(self, name="test.mp4", size="270x480", duration=2):
        path = os.path.join(self._tmp, name)
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=%s:rate=24" % size,
            "-f", "lavfi", "-i", "sine",
            "-t", str(duration), "-shortest", "-pix_fmt", "yuv420p", path,
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return path
