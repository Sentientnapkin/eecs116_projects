"""Preflight must reject unknown proof and detect modified packaged binaries."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from ...preflight import audit


class PreflightTests(unittest.TestCase):
    def setup_package(self,path):
        wasm=path/'solution.wasm'; wasm.write_bytes(b'\0asm\x01\0\0\0')
        digest=hashlib.sha256(wasm.read_bytes()).hexdigest()
        build={'wasm_sha256':digest,'commands':[['clang++','-c','guest.cpp']],
           'sources':{'guest.cpp':'test'},'dependencies':{'lib.a':'test'}}
        (path/'build.json').write_text(json.dumps(build))
        files={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (wasm,path/'build.json')}
        manifest={'wasm_file':wasm.name,'wasm_sha256':digest,'files':files,'evidence':{}}
        (path/'manifest.json').write_text(json.dumps(manifest))
        return wasm

    def test_smoke_is_not_release_and_unknown_abi_stays_unknown(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as temp:
            path=Path(temp); self.setup_package(path)
            smoke=audit(path,smoke=True)
            self.assertTrue(smoke['pass'])
            self.assertFalse(smoke['release_pass'])
            self.assertEqual(smoke['checks'][-1]['status'],'not_checked')
            release=audit(path)
            self.assertFalse(release['pass'])
            self.assertTrue(all(c['status']=='not_checked' for c in release['checks']))

    def test_binary_tampering_fails_smoke(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as temp:
            path=Path(temp); wasm=self.setup_package(path)
            wasm.write_bytes(wasm.read_bytes()+b'changed')
            report=audit(path,smoke=True)
            self.assertFalse(report['pass'])
            self.assertEqual(report['checks'][0]['status'],'fail')

if __name__=='__main__':
    unittest.main()
