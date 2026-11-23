import csv
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from pipeline.ai_job_map import label

PACKET = {"name": "t", "snapshot_date": "2026-11-11", "config_sha256": "x",
          "roles": [{"n": 1, "posting_id": "greenhouse:acme:1", "title": "ML Engineer", "requirement_text": "Train models.", "full_ad": ["About Acme", "Train models."]},
                    {"n": 2, "posting_id": "greenhouse:acme:2", "title": "Recruiter", "requirement_text": "Hire people.", "full_ad": ["Hire people."]}]}


class TestLabelServer(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.labels = os.path.join(self.dir, "t.labels.csv")
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), label.make_handler(PACKET, self.labels, 0))
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def _post(self, body, headers=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/label", data=json.dumps(body).encode(),
                                     headers=headers or {"Content-Type": "application/json"}, method="POST")
        return urllib.request.urlopen(req)

    def test_page_gets_no_scores_or_firm_ids(self):
        state = urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/state").read().decode()
        self.assertNotIn("posting_id", state)
        self.assertNotIn("acme:", state)
        self.assertNotIn("omega", state)

    def test_label_is_saved_and_time_accumulates(self):
        self._post({"n": 1, "label": "builds", "note": "trains models", "seconds": 30})
        self._post({"n": 1, "label": "works_with", "note": "", "seconds": 10})
        rows = list(csv.DictReader(open(self.labels)))
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["posting_id"], rows[0]["label"], rows[0]["seconds_on_role"]), ("greenhouse:acme:1", "works_with", "40"))
        self.assertEqual(rows[0]["codebook_version"], label.CODEBOOK_VERSION)

    def test_bad_labels_and_foreign_origins_are_refused(self):
        with self.assertRaises(urllib.error.HTTPError):
            self._post({"n": 1, "label": "maybe"})
        with self.assertRaises(urllib.error.HTTPError):
            self._post({"n": 9, "label": "none"})
        with self.assertRaises(urllib.error.HTTPError):
            self._post({"n": 1, "label": "none"}, {"Content-Type": "application/json", "Origin": "https://evil.example"})
        self.assertFalse(os.path.exists(self.labels))


if __name__ == "__main__":
    unittest.main()
