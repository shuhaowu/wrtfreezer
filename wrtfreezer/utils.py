from __future__ import absolute_import

from contextlib import contextmanager
import hashlib
import logging
import os
import os.path

logging_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s: %(message)s")
IMAGE_BUILDER_DIR_NAME = "imagebuilder"


@contextmanager
def cd(newdir):
  olddir = os.getcwd()
  os.chdir(os.path.expanduser(newdir))
  try:
    yield
  finally:
    os.chdir(olddir)


def md5_file(filename):
  md5 = hashlib.md5()
  with open(filename, "rb") as f:
    while True:
      buf = f.read(2 ** 20)
      if not buf:
        break
      md5.update(buf)

  return md5.hexdigest()


def get_targets_dir(out_dir):
  return os.path.join(out_dir, "targets")


def get_intermediates_dir(out_dir):
  return os.path.join(out_dir, "intermediates")
