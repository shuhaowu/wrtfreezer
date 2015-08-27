#!/usr/bin/env python

from distutils.core import setup

with open('requirements.txt') as f:
  requirements = f.read().splitlines()

setup(
  name="wrtfreezer",
  version="0.1",
  description="A simple utility to mass build OpenWRT images.",
  author="Shuhao Wu",
  license="AGPL",
  url="https://github.com/shuhaowu/wrtfreezer",
  packages=["wrtfreezer"],
  scripts=["wrtbuild"],
  requires=requirements,
)
