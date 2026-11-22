"""Unmodified v700b training recipe with audited inputs and isolated output."""
import json, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent; SM=HERE.parent
sys.path[:0]=[str(SM/'learnvel'),str(SM/'learned_c'),str(SM/'learned')]
import lv_train as L
D=json.load(open(HERE/'tables/data_audit.json'))
L.OUT=HERE/'runs'
L.train_files=lambda pools:[Path(r['cache']) for r in D['train'] if r['pool'] in pools]
L.split2.load_rows=lambda:D['val']
L.main()
