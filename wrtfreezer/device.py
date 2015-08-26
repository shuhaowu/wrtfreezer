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

    default_device_type = "{}-{}-{}-{}".format(self.release, self.version, self.arch, self.type)
    self.device_type = self.config.get("device_type", default_device_type)
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

      self.logger.info("invoking build with {}".format(cmd))
      subprocess.check_call(cmd)

    self.logger.info("build completed")

    output_name = self.config.get("output_name")
    if output_name:
      target_dir = os.path.abspath(os.path.join(get_targets_dir(self.out_dir), self.device_name))
      if not os.path.exists(target_dir):
        os.mkdir(target_dir, 0755)

      with cd(target_dir):
        factory_filename = "openwrt-{}-{}-{}-v1-squashfs-factory.bin".format(self.arch, self.type, output_name)
        sysupgrade_filename = "openwrt-{}-{}-{}-v1-squashfs-sysupgrade.bin".format(self.arch, self.type, output_name)
        squashfs_factory_path = os.path.join(builder_dir, "bin", self.arch, factory_filename)
        squashfs_sysupgrade_path = os.path.join(builder_dir, "bin", self.arch, sysupgrade_filename)

        if os.path.exists(factory_filename):
          os.remove(factory_filename)

        if os.path.exists(sysupgrade_filename):
          os.remove(sysupgrade_filename)

        subprocess.check_call(["ln", squashfs_factory_path, factory_filename])
        subprocess.check_call(["ln", squashfs_sysupgrade_path, squashfs_sysupgrade_path])

      self.logger.info("factory: {}".format(squashfs_factory_path))
      self.logger.info("sysupgrade: {}".format(squashfs_sysupgrade_path))
    else:
      self.logger.info("outdir: {}".format(os.path.join(builder_dir, "bin", self.arch)))
