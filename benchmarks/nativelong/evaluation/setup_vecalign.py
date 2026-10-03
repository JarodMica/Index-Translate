#!/usr/bin/env python3
"""Compile the bundled VecAlign extension for this Python/platform."""
import os
from pathlib import Path

import numpy
from Cython.Build import cythonize
from setuptools import Extension, setup

if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent / "vendor/segale")
    setup(name="nativelong-vecalign", ext_modules=cythonize([
        Extension("vecalign.dp_core", ["vecalign/dp_core.pyx"],
                  include_dirs=[numpy.get_include()])], build_dir="build/cython"),
        script_args=["build_ext", "--inplace", "--build-temp", "build/temp"])
