import unittest
from server import race_points
class ScoreTest(unittest.TestCase):
 def test_twenty_equal_bands_at_multiple_durations(self):
  for duration in (20,200,351.5):
   for i in range(20):
    self.assertEqual(race_points((i+.5)*duration/20,duration),20-i)
 def test_clamps_and_invalid(self):
  self.assertEqual(race_points(-1,200),20)
  self.assertEqual(race_points(200,200),0)
  for elapsed,duration in [(10,0),(10,None),(float('nan'),10),(1,float('inf'))]:self.assertEqual(race_points(elapsed,duration),0)
