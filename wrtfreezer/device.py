from __future__ import absolute_import

import logging
import os.path
import subprocess

from .utils import get_targets_dir, get_intermediates_dir, IMAGE_BUILDER_DIR_NAME, cd, logging_formatter


class Device(object):
  def __init__(self, path, config, out_dir):
    self.path = os.path.abspath(path)
    self.config = config
    self.out_dir = out_dir

    try:
      self.release = self.config["release"]
      self.version = self.config["version"]
      self.arch = self.config["arch"]
      self.type = self.config["type"]
    except KeyError:
      raise ValueError("configuration is not valid, missing release, version, arch, type, or profile")

    self.device_type = "{}-{}-{}-{}".format(self.release, self.version, self.arch, self.type)
    self.device_name = self.config["profile"]

    self.logger = logging.getLogger(self.device_name)
    handler = logging.StreamHandler()
    handler.setFormatter(logging_formatter)
    self.logger.addHandler(handler)
    self.logger.setLevel(logging.DEBUG)

  def build_image(self):
    builder_dir = os.path.join(get_intermediates_dir(self.out_dir), self.device_type, IMAGE_BUILDER_DIR_NAME)
    builder_dir = os.path.abspath(builder_dir)

    self.logger.info("starting build")

    with cd(builder_dir):
      cmd = ["make", "image", "PROFILE={}".format(self.device_name)]

      packages = self.config.get("packages")
      if packages:
        cmd.append('PACKAGES={}'.format(" ".join(self.config["packages"])))

      files_directory = os.path.join(self.path, "files")
      if os.path.exists(files_directory):
        cmd.append("FILES={}".format(files_directory))

      subprocess.check_call(cmd)

    # target_dir = os.path.abspath(os.pathjoin(get_targets_dir(self.out_dir), self.device_name))
