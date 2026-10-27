"""Small independent checks for the manuscript's added event diagnostics."""
import unittest
from final_simulation_study import outcomes
from deda.metrics import Event
from deda.policy import Alert

class Diagnostics(unittest.TestCase):
 def test_wrong_class_detection_is_not_correct_class_detection(self):
  m,rows=outcomes([Alert(200,'DIR',1,4,180,0)],[Event(100,400,0,0)],10000,1,'Main','B')
  self.assertEqual(m['miss_rate'],0)
  self.assertEqual(m['correct_class_detection'],0)
  self.assertEqual(m['wrong_dir_per_event'],1)
  self.assertEqual(rows[0]['correct_class'],False)
 def test_missing_alert_and_update_do_not_establish_detection(self):
  m,rows=outcomes([Alert(200,'UPDATE',0,1,0,0)],[Event(100,400,0,0)],10000,1,'Main','B')
  self.assertEqual(m['miss_rate'],1)
  self.assertIsNone(m['latency_max_ms'])
  self.assertEqual(m['notifications_per_total_hour'],0)
 def test_boundary_motor_set_and_late_warning_are_reported_separately(self):
  m,rows=outcomes([Alert(500,'DIR',0,3,40,2)],[Event(100,400,0,0)],10000,1,'Main','DEDA')
  self.assertEqual(m['wrong_dir_per_event'],0)
  self.assertEqual(m['miss_or_late_rate'],1)
  self.assertEqual(m['late_with_episode_wait'],1)
  self.assertEqual(m['late_episode_open_after_deadline'],0)

if __name__=='__main__':unittest.main()
