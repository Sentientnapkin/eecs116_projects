"""build.py SRC NAME ["DEFINES"] -> agents/smallnet/builds/NAME/solution.wasm (reuses netv2/tools/build.py toolchain)."""
import sys
from pathlib import Path
sys.path.insert(0, '/data/backups/rganapa/Sebastian/gen3/agents/netv2/tools')
import build as B
B.OUT = Path('/data/backups/rganapa/Sebastian/gen3/agents/smallnet/builds')
build = B.build
if __name__ == '__main__':
    print(*build(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ''))
