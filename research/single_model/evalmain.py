"""`python evalmain.py evaluate ...` = `python -m viobench evaluate ...` with the decoded-frame cache installed."""
import sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import png_cache
png_cache.install()
from viobench.tools.cli import main
sys.exit(main(sys.argv[1:]))
