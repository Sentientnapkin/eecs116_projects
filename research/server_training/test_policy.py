import json
from pathlib import Path
import tempfile
import unittest
from .prepare import choose


class PolicyTests(unittest.TestCase):
    def test_no_selected_or_dev_scene_in_training(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'bench').mkdir()
            roster={'flights':[{'scene':'train-scene','split':'train'},{'scene':'dev-scene','split':'dev'},{'scene':'test-scene','split':'test'}]}
            (root/'campaign.json').write_text(json.dumps(roster));(root/'selection.json').write_text(json.dumps({'selected':['fast-selected','fast-dev']}))
            items=[('fast-good','train-scene','seen'),('fastmid-good','train-scene','seen'),('fast-selected','train-scene','seen'),('fast-dev','dev-scene','dev'),('fast-test','test-scene','seen')]
            for id,scene,group in items:(root/'bench'/f'{id}.json').write_text(json.dumps({'id':id,'scene':scene,'group':group}))
            train, heldout=choose({'campaign_roster':str(root/'campaign.json'),'selection':str(root/'selection.json'),'raw_root':str(root),'seed':217,'per_start':1})
            self.assertEqual({r['id'] for r in train},{'fast-good','fastmid-good'})
            self.assertEqual({r['id'] for r in heldout},{'fast-dev'})

    def test_overlap_roster_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=root/'campaign.json';p.write_text(json.dumps({'flights':[{'scene':'same','split':'train'},{'scene':'same','split':'test'}]}))
            with self.assertRaisesRegex(ValueError,'overlap'): choose({'campaign_roster':str(p)})


if __name__=='__main__': unittest.main()
