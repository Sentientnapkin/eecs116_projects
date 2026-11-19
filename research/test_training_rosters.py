"""Read-only roster contract: SHA identity remains distinct from parent dependence."""
import unittest
from training_finish_eval import records
class RosterIdentity(unittest.TestCase):
 def test_parent_counts_and_original_record_identity(self):
  expected={'dev':(14,7),'campaign-dev':(120,60),'proxy-val':(69,68),'public':(10,10)}
  for policy in ('rolling','static08','kf_grid_native'):
   for roster,(n,parents) in expected.items():
    _,rows,_=records(policy,roster)
    self.assertEqual(len(rows),n)
    keys=[r.get('derived_from',r['sha256']) for r in rows]
    self.assertEqual(len(set(keys)),n)
    ids=[r.get('parent_sha256') or r.get('parent_file') for r in rows]
    self.assertTrue(all(ids))
    self.assertEqual(len(set(ids)),parents)
if __name__=='__main__':unittest.main()
