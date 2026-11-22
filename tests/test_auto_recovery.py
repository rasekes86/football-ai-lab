from datetime import datetime, timedelta, timezone
import unittest
from football_ai_lab.recovery import needs_recovery, can_dispatch

NOW=datetime(2026,11,22,12,0,tzinfo=timezone.utc)

class RecoveryTests(unittest.TestCase):
    def test_recent_update_does_not_trigger_more_calls(self):
        self.assertFalse(needs_recovery({"calculado_utc":(NOW-timedelta(hours=25)).isoformat()},NOW))
        self.assertTrue(needs_recovery({"calculado_utc":(NOW-timedelta(hours=27)).isoformat()},NOW))
        self.assertFalse(needs_recovery({"calculado_utc":(NOW+timedelta(hours=1)).isoformat()},NOW))

    def test_missing_status_is_recoverable_but_requires_actions_verification(self):
        self.assertTrue(needs_recovery({},NOW))
        self.assertTrue(can_dispatch([],NOW))

    def test_active_workflow_and_recent_dispatch_prevent_duplicates(self):
        active=[{"status":"queued","event":"schedule","createdAt":NOW.isoformat()}]
        self.assertFalse(can_dispatch(active,NOW))
        manual=[{"status":"completed","event":"workflow_dispatch",
                 "createdAt":(NOW-timedelta(hours=11)).isoformat()}]
        self.assertFalse(can_dispatch(manual,NOW))
        old=[{"status":"completed","event":"workflow_dispatch",
              "createdAt":(NOW-timedelta(hours=13)).isoformat()}]
        self.assertTrue(can_dispatch(old,NOW))

    def test_very_recent_failed_run_still_gets_a_cooldown(self):
        row=[{"status":"completed","event":"schedule",
              "createdAt":(NOW-timedelta(minutes=40)).isoformat()}]
        self.assertFalse(can_dispatch(row,NOW))
        row[0]["createdAt"]=(NOW-timedelta(hours=3)).isoformat()
        self.assertTrue(can_dispatch(row,NOW))

if __name__=="__main__":
    unittest.main()
