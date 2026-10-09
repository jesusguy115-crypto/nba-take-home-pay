import base64
import hashlib
import json
from pathlib import Path
import unittest
from player_context import context
ASSETS = Path(__file__).resolve().parents[1] / 'assets'
class PlayerContextTests(unittest.TestCase):
    def test_current_and_future(self):
        c = context('6287')
        self.assertEqual(c['current'][0]['total_usd'],62587158)
        self.assertEqual(c['current'][0]['start_year'],2026)
        self.assertEqual(c['extensions'][0]['total_usd'],115856000)
        self.assertEqual(c['extensions'][0]['start_year'],2027)
        self.assertEqual(c['extensions'][0]['end_year'],2028)
    def test_unknown(self):
        c=context('nonexistent')
        self.assertEqual(c['status'],'unverified')
        self.assertIn('尚未核实',c['current_summary'])
        self.assertIn('尚未核实',c['extension_summary'])
        self.assertEqual(c['current'],[])
    def test_media_integrity(self):
        m=json.loads((ASSETS/'player-media-2026-27.json').read_text())
        for name in m.get('portrait_parts', []):
            m['players'].update(json.loads((ASSETS/name).read_text())['players'])
        self.assertEqual(len(m['players']),520)
        self.assertEqual(len(m['teams']),30)
        hashes=[]
        for r in list(m['players'].values())+list(m['teams'].values()):
            raw=base64.b64decode(r['image_data'].split(',',1)[1])
            self.assertEqual(raw[:8],b'\x89PNG\r\n\x1a\n')
            digest=hashlib.sha256(raw).hexdigest()
            self.assertEqual(digest,r['sha256'])
            hashes.append(digest)
        self.assertEqual(len(set(hashes[:520])),520)
if __name__=='__main__': unittest.main()
