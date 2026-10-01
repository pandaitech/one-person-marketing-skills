from __future__ import annotations

import os

from helpers import StudioTestCase

from studio_core import store


class ClipLifecycleTest(StudioTestCase):
    def test_create_comment_send_claim_version_resolve_approve(self):
        clip = store.create_clip(title="V02 Two Problems", workdir="/tmp/x")
        self.assertEqual(clip["status"], "drafting")
        self.assertTrue(clip["id"].startswith("v02-two-problems"))

        # original version: n starts at 0 for kind=original
        clip, v0 = store.add_clip_version(clip["id"], "/tmp/x/orig.mp4", kind="original")
        self.assertEqual(v0["n"], 0)
        self.assertEqual(clip["status"], "review")

        # a render is v1 (first non-original)
        clip, v1 = store.add_clip_version(clip["id"], "/tmp/x/v1.mp4", kind="render")
        self.assertEqual(v1["n"], 1)

        # director drafts a note
        clip, c1 = store.add_clip_comment(clip["id"], version=1, text="remove the intro",
                                           t=12.3, author="director")
        self.assertEqual(c1["status"], "draft")
        self.assertTrue(store.clip_has_director_drafts(store.get_clip(clip["id"])))

        # send -> sent, clip queued, agent queued
        clip, n_sent = store.send_clip_notes(clip["id"])
        self.assertEqual(n_sent, 1)
        self.assertEqual(clip["status"], "queued")
        self.assertEqual(clip["agent"]["state"], "queued")
        sent_comment = next(c for c in clip["comments"] if c["id"] == c1["id"])
        self.assertEqual(sent_comment["status"], "sent")

        # claim -> working
        clip = store.claim_clip(clip["id"], message="on it")
        self.assertEqual(clip["status"], "working")
        self.assertEqual(clip["agent"]["state"], "working")

        # add-version with addresses -> comment addressed, clip review, agent idle
        clip, v2 = store.add_clip_version(clip["id"], "/tmp/x/v2.mp4", kind="render",
                                           addresses=[c1["id"]], notes="removed intro")
        self.assertEqual(v2["n"], 2)
        self.assertEqual(clip["status"], "review")
        self.assertEqual(clip["agent"]["state"], "idle")
        addressed = next(c for c in clip["comments"] if c["id"] == c1["id"])
        self.assertEqual(addressed["status"], "addressed")
        self.assertEqual(addressed["addressed_in"], 2)

        # resolve
        clip, _ = store.update_clip_comment(clip["id"], c1["id"], {"status": "resolved"})
        resolved = next(c for c in clip["comments"] if c["id"] == c1["id"])
        self.assertEqual(resolved["status"], "resolved")

        # reopen -> draft
        clip, _ = store.update_clip_comment(clip["id"], c1["id"], {"status": "draft"})
        reopened = next(c for c in clip["comments"] if c["id"] == c1["id"])
        self.assertEqual(reopened["status"], "draft")

        # approve
        clip = store.approve_clip(clip["id"], 2)
        self.assertEqual(clip["status"], "approved")
        self.assertEqual(clip["approved_version"], 2)

        # unapprove
        clip = store.unapprove_clip(clip["id"])
        self.assertEqual(clip["status"], "review")

    def test_version_numbering_without_original(self):
        clip = store.create_clip(title="No original clip")
        clip, v1 = store.add_clip_version(clip["id"], "/tmp/v1.mp4", kind="render")
        self.assertEqual(v1["n"], 1)
        clip, v2 = store.add_clip_version(clip["id"], "/tmp/v2.mp4", kind="render")
        self.assertEqual(v2["n"], 2)

    def test_unique_clip_id_from_title(self):
        c1 = store.create_clip(title="Same Title")
        c2 = store.create_clip(title="Same Title")
        self.assertNotEqual(c1["id"], c2["id"])
        self.assertTrue(c2["id"].startswith("same-title"))

    def test_delete_comment_only_draft(self):
        clip = store.create_clip(title="Delete test")
        clip, c1 = store.add_clip_comment(clip["id"], version=0, text="hello")
        clip, n = store.send_clip_notes(clip["id"])
        clip, result = store.delete_clip_comment(clip["id"], c1["id"])
        self.assertFalse(result["ok"])
        clip, result = store.delete_clip_comment(clip["id"], c1["id"], force=True)
        self.assertTrue(result["ok"])

    def test_events_appended(self):
        clip = store.create_clip(title="Events clip")
        events = store.list_events(limit=10, clip=clip["id"])
        self.assertTrue(any(e["type"] == "clip_created" for e in events))


class RecordingLifecycleTest(StudioTestCase):
    def test_recording_proposal_approve_creates_clip(self):
        rec = store.create_recording(title="Meta Ads Class", file="/tmp/rec.mp4",
                                      transcript="/tmp/transcript.json")
        self.assertEqual(rec["status"], "new")

        rec, c1 = store.add_recording_comment(rec["id"], text="find clips about pricing", t=None)
        self.assertEqual(c1["status"], "draft")

        rec, n_sent = store.send_recording_notes(rec["id"])
        self.assertEqual(n_sent, 1)
        self.assertEqual(rec["status"], "queued")
        self.assertEqual(rec["agent"]["state"], "queued")

        rec = store.claim_recording(rec["id"])
        self.assertEqual(rec["status"], "working")

        rec, p1 = store.add_proposal(
            rec["id"], title="2 Masalah Buat Meta Ads", ranges=[[674.14, 693.64], [693.98, 731.36]],
            hook="Tapi biasanya...", summary="setup -> point -> payoff", score=8.5,
            addresses=[c1["id"]])
        self.assertEqual(p1["id"], "p1")
        self.assertEqual(p1["status"], "proposed")
        addressed = next(c for c in rec["comments"] if c["id"] == c1["id"])
        self.assertEqual(addressed["status"], "addressed")

        rec = store.proposals_ready(rec["id"])
        self.assertEqual(rec["status"], "proposed")
        self.assertEqual(rec["agent"]["state"], "idle")

        rec, proposal, clip = store.approve_proposal(rec["id"], p1["id"])
        self.assertEqual(proposal["status"], "approved")
        self.assertIsNotNone(clip)
        self.assertEqual(proposal["clip_id"], clip["id"])
        self.assertEqual(clip["status"], "queued")
        self.assertEqual(clip["agent"]["state"], "queued")
        self.assertIn("renders", clip["workdir"])
        self.assertIn(clip["id"], clip["workdir"])
        self.assertIn("ranges", clip["source"])
        self.assertIn("11:14.1", clip["brief"])  # 674.14s formatted as m:ss.s

        # unique id: re-running approve on same proposal is idempotent
        rec2, proposal2, clip2 = store.approve_proposal(rec["id"], p1["id"])
        self.assertEqual(clip2["id"], clip["id"])

    def test_reject_proposal(self):
        rec = store.create_recording(title="Rej Rec", file="/tmp/rec2.mp4")
        rec, p1 = store.add_proposal(rec["id"], title="Bad idea", ranges=[[0, 1]])
        rec, p1 = store.reject_proposal(rec["id"], p1["id"])
        self.assertEqual(p1["status"], "rejected")

    def test_proposal_ids_increment(self):
        rec = store.create_recording(title="Ids Rec", file="/tmp/rec3.mp4")
        rec, p1 = store.add_proposal(rec["id"], title="A", ranges=[[0, 1]])
        rec, p2 = store.add_proposal(rec["id"], title="B", ranges=[[1, 2]])
        self.assertEqual(p1["id"], "p1")
        self.assertEqual(p2["id"], "p2")
