#!/usr/bin/env python
from __future__ import print_function

import argparse
import json
import os.path
import sys

import wrtfreezer


def get_options():
  parser = argparse.ArgumentParser(description="builds OpenWRT images")
  parser.add_argument("dir", nargs="?", default=None, help="path to the working directory for all the builds")
  parser.add_argument("--config", nargs="?", default="wrtfreezer.conf.json", help="path to the config file")
  args = parser.parse_args()
  return args, parser


def main():
  args, parser = get_options()
  if not os.path.isfile(args.config):
    print("error: {} is not a valid file".format(args.config), file=sys.stderr)
    parser.print_help(file=sys.stderr)
    sys.exit(1)

  with open(args.config) as f:
    config = json.load(f)

  workdir = args.dir
  if not workdir:
    workdir = config.get("workdir", ".")

  if not os.path.isdir(workdir):
    print("error: {} is not a valid directory".format(workdir), file=sys.stderr)
    parser.print_help(file=sys.stderr)
    sys.exit(1)

  for device_config in config["devices"]:
    image = wrtfreezer.Image(workdir, device_config)
    image.setup()
    image.build()

if __name__ == "__main__":
  main()
