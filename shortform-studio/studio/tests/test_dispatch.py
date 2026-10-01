from __future__ import annotations

import time

from helpers import StudioTestCase

from studio_core import dispatch, store


def _wait_until(predicate, timeout=5.0, interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class DispatchTest(StudioTestCase):
    def test_dispatch_without_new_version_ends_in_error(self):
        store.update_settings({"dispatch_command": ["/bin/sh", "-c", "echo hi; exit 0"]})
        clip = store.create_clip(title="Dispatch Clip", workdir="/tmp")
        clip, _ = store.add_clip_comment(clip["id"], version=0, text="a note")
        store.send_clip_notes(clip["id"])  # real flow: send puts the clip in queued/agent-queued
        run_id, log_path = dispatch.dispatch_clip(clip["id"])
        self.assertTrue(run_id)

        ok = _wait_until(lambda: store.get_clip(clip["id"])["agent"]["state"] != "working")
        self.assertTrue(ok, "watcher thread did not finish in time")
        final = store.get_clip(clip["id"])
        self.assertEqual(final["agent"]["state"], "error")
        self.assertEqual(final["status"], "queued")
        with open(log_path) as f:
            self.assertIn("hi", f.read())

    def test_dispatch_missing_executable_raises(self):
        store.update_settings({"dispatch_command": ["/no/such/executable-xyz", "{prompt}"]})
        clip = store.create_clip(title="Missing Exe Clip")
        with self.assertRaises(dispatch.DispatchError):
            dispatch.dispatch_clip(clip["id"])

    def test_reconcile_marks_dead_pid_as_error(self):
        clip = store.create_clip(title="Dead Pid Clip")
        store.claim_clip(clip["id"])
        store.set_clip_agent(clip["id"], {"pid": 999999, "state": "working"})
        dispatch.reconcile_on_start()
        final = store.get_clip(clip["id"])
        self.assertEqual(final["agent"]["state"], "error")
        self.assertEqual(final["status"], "queued")
