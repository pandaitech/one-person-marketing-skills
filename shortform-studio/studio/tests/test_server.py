from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request

from helpers import StudioTestCase

from studio_core import media, paths, server, store


class ServerTestCase(StudioTestCase):
    def setUp(self):
        super().setUp()
        self.httpd = server.make_server(port=0)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
        super().tearDown()

    def url(self, path):
        return "http://127.0.0.1:%d%s" % (self.port, path)

    def request(self, method, path, body=None, headers=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.url(path), data=data, method=method)
        req.add_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            resp = urllib.request.urlopen(req)
            return resp.getcode(), resp.read(), dict(resp.getheaders())
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.getheaders())


class ApiSmokeTest(ServerTestCase):
    def test_state_post_clip_comment_send(self):
        status, body, _ = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        state = json.loads(body)
        self.assertIn("settings", state)
        self.assertIn("counts", state)
        self.assertEqual(state["clips"], [])

        status, body, _ = self.request("POST", "/api/clips", {"title": "Server Test Clip"})
        self.assertEqual(status, 200)
        clip = json.loads(body)
        clip_id = clip["id"]

        status, body, _ = self.request(
            "POST", "/api/clips/%s/comments" % clip_id,
            {"version": 0, "t": 1.5, "text": "fix this"})
        self.assertEqual(status, 200)
        comment = json.loads(body)
        self.assertEqual(comment["status"], "draft")

        status, body, _ = self.request("POST", "/api/clips/%s/send" % clip_id)
        self.assertEqual(status, 200)
        sent = json.loads(body)
        self.assertEqual(sent["status"], "queued")

        status, body, _ = self.request("GET", "/api/clips/%s" % clip_id)
        self.assertEqual(status, 200)
        full = json.loads(body)
        self.assertEqual(full["comments"][0]["status"], "sent")

    def test_unknown_clip_404(self):
        status, body, _ = self.request("GET", "/api/clips/does-not-exist")
        self.assertEqual(status, 404)
        self.assertIn("error", json.loads(body))

    def test_bad_input_400(self):
        status, body, _ = self.request("POST", "/api/clips", {})
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(body))

    def test_static_index(self):
        status, body, headers = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("Content-Type", ""))


class MediaRangeTest(ServerTestCase):
    def setUp(self):
        super().setUp()
        self.video = self.make_test_video()
        store.update_settings({"media_roots": [self._tmp]})
        clip = store.create_clip(title="Range Clip")
        self.clip_id = clip["id"]
        info = media.probe(self.video)
        store.add_clip_version(self.clip_id, self.video, kind="original", probe=info)

    def test_range_request_206(self):
        status, body, headers = self.request(
            "GET", "/media/%s/0" % self.clip_id, headers={"Range": "bytes=0-99"})
        self.assertEqual(status, 206)
        self.assertEqual(len(body), 100)
        self.assertEqual(headers.get("Accept-Ranges"), "bytes")
        self.assertTrue(headers.get("Content-Range", "").startswith("bytes 0-99/"))

    def test_full_request_200(self):
        status, body, headers = self.request("GET", "/media/%s/0" % self.clip_id)
        self.assertEqual(status, 200)
        self.assertEqual(len(body), os.path.getsize(self.video))

    def test_thumb_and_waveform_and_filmstrip(self):
        status, body, headers = self.request("GET", "/thumb/%s/0.jpg" % self.clip_id)
        self.assertEqual(status, 200)
        self.assertEqual(body[:3], b"\xff\xd8\xff")

        status, body, headers = self.request("GET", "/waveform/%s/0.png" % self.clip_id)
        self.assertEqual(status, 200)
        self.assertEqual(body[:8], b"\x89PNG\r\n\x1a\n")

        status, body, headers = self.request("GET", "/filmstrip/%s/0.jpg" % self.clip_id)
        self.assertEqual(status, 200)
        self.assertEqual(body[:3], b"\xff\xd8\xff")

    def test_media_root_restriction(self):
        outside = "/etc/hosts"
        clip = store.create_clip(title="Outside Clip")
        store.add_clip_version(clip["id"], outside, kind="original",
                                probe={"duration": 1, "width": 1, "height": 1, "size": 1})
        status, body, _ = self.request("GET", "/media/%s/0" % clip["id"])
        self.assertIn(status, (403, 404))
