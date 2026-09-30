"""Compatibility entry point for the unified demo figure generator."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name('render_benchmark_overviews.py')),run_name='__main__')
