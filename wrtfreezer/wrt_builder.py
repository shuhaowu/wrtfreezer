from __future__ import absolute_import, print_function

import logging
import json
import os
import os.path
import subprocess
import shutil

import requests

from .utils import logging_formatter, get_intermediates_dir, get_targets_dir, md5_file, cd, IMAGE_BUILDER_DIR_NAME
from .device import Device


CHUNK_SIZE = 1024 * 1024  # 1MB
BUILDER_FILENAME = "imagebuilder.tar.bz2"


class WrtBuilder(object):
  def __init__(self, args, parser):
    self.args = args
    self.parser = parser
    self.logger = logging.getLogger("wrt_builder")
    handler = logging.StreamHandler()
    handler.setFormatter(logging_formatter)
    self.logger.addHandler(handler)
    self.logger.setLevel(logging.DEBUG)

    self.config = self._get_global_config()
    self._devices = self._discover_devices_from_directory()

  def build(self):
    self._setup_out_dir()
    self._ensure_image_generators_exist()

    if not self.args.yes:
      self._prompt_for_build_confirmation()

    for name, device in self._devices.iteritems():
      device.build_image()

  def clean(self):
    pass

  def _get_global_config(self):
    global_config_path = os.path.join(self.args.devices_dir, "config.json")
    if not os.path.exists(global_config_path):
      raise RuntimeError("cannot find global config at {}".format(global_config_path))

    with open(global_config_path) as f:
      config = json.load(f)

    return config

  def _discover_devices_from_directory(self):
    self.logger.debug("discovering devices from directory")
    devices = {}
    for fn in os.listdir(self.args.devices_dir):
      path = os.path.join(self.args.devices_dir, fn)
      if not os.path.isdir(path):
        continue

      configpath = os.path.join(path, "device.json")
      if not os.path.isfile(configpath):
        continue

      self.logger.debug("discovered {}".format(fn))
      with open(configpath) as f:
        device_config = json.load(f)
        devices[fn] = Device(path, device_config, self.args.out_dir)

    return devices

  def _setup_out_dir(self):
    self._intermediates_dir = get_intermediates_dir(self.args.out_dir)
    self._targets_dir = get_targets_dir(self.args.out_dir)

    if not os.path.exists(self._intermediates_dir):
      self.logger.debug("creating intermediates build directory")
      os.mkdir(self._intermediates_dir, 0755)

    if not os.path.exists(self._targets_dir):
      self.logger.debug("creating target output directory")
      os.mkdir(self._targets_dir, 0755)

    for name in self._devices:
      device_out_path = os.path.join(self._targets_dir, name)
      if not os.path.exists(device_out_path):
        os.mkdir(device_out_path, 0755)

  def _ensure_image_generators_exist(self):
    for name, device in self._devices.iteritems():
      intermediates_device_dir = os.path.join(self._intermediates_dir, device.device_type)
      if not os.path.exists(intermediates_device_dir):
        os.mkdir(intermediates_device_dir, 0755)

      self._download_builder(intermediates_device_dir, device)
      self._setup_repositories_conf(intermediates_device_dir, device)

  def _download_builder(self, builder_dir, device):
    filename = "OpenWrt-ImageBuilder-{}_{}-for-linux-x86_64.tar.bz2".format(device.arch, device.type)
    filename_fallback = "OpenWrt-ImageBuilder-{}-for-linux-x86_64.tar.bz2".format(device.arch)

    self.logger.debug("checking if {} image generator is up to date".format(device.device_type))
    r = requests.get("https://downloads.openwrt.org/{}/{}/{}/{}/md5sums".format(device.release, device.version, device.arch, device.type))
    if r.status_code != 200:
      raise RuntimeError("cannot get md5sums from openwrt...")

    md5sums = filter(lambda l: filename in l or filename_fallback in l, r.text.strip().split("\n"))
    md5sums = [line.split(" ")[0].strip() for line in md5sums]

    # make sure that the file doesn't already exists...
    builder_filename = os.path.join(builder_dir, BUILDER_FILENAME)
    if os.path.exists(builder_filename):
      if md5_file(builder_filename) in md5sums:
        self.logger.debug("{} image generator is up to date, skipping download".format(device.device_type))
        return False

    url_primary = "https://downloads.openwrt.org/{}/{}/{}/{}/{}".format(device.release, device.version, device.arch, device.type, filename)
    url_fallback = "https://downloads.openwrt.org/{}/{}/{}/{}/".format(device.release, device.version, device.arch, device.type, filename_fallback)

    self.logger.debug("downloading image generator...")
    r = requests.get(url_primary)
    if r.status_code == 404:
      r = requests.get(url_fallback)
      if r.status_code == 404:
        raise ValueError("cannot find image builder for {}/{}/{}/{}".format(self.release, self.version, self.arch, self.type))

    with open(builder_filename, "wb") as f:
      count = 0
      for chunk in r.iter_content(CHUNK_SIZE):
        f.write(chunk)
        count += 1
        if count % 5 == 0:
          self.logger.debug("{}MB downloaded...".format(count))

    self.logger.debug("{} image generator downloaded, verifying...".format(device.device_type))
    downloaded_md5 = md5_file(builder_filename)
    if downloaded_md5 not in md5sums:
      raise RuntimeError("validation of download for {} failed: expected {}, got {}".format(device.device_type, md5sums, downloaded_md5))

    self.logger.debug("{} image generator verified, untarring...".format(device.device_type))
    with cd(builder_dir):
      subprocess.check_call(["tar", "-xjf", BUILDER_FILENAME])

      for path in os.listdir("."):
        if path.startswith("OpenWrt-ImageBuilder") and os.path.isdir(path):
          shutil.move(path, IMAGE_BUILDER_DIR_NAME)
          break

    return True

  def _setup_repositories_conf(self, intermediates_device_dir, device):
    extra_repositories = self.config.get("repositories")
    if extra_repositories:
      extra_repositories = "\n".join(extra_repositories)
    else:
      extra_repositories = ""

    default_repo = """
src/gz {release}_base https://downloads.openwrt.org/{release}/{version}/{arch}/{type}/packages/base
src/gz {release}_luci https://downloads.openwrt.org/{release}/{version}/{arch}/{type}/packages/luci
src/gz {release}_management https://downloads.openwrt.org/{release}/{version}/{arch}/{type}/packages/management
src/gz {release}_packages https://downloads.openwrt.org/{release}/{version}/{arch}/{type}/packages/packages
src/gz {release}_routing https://downloads.openwrt.org/{release}/{version}/{arch}/{type}/packages/routing
src/gz {release}_telephony https://downloads.openwrt.org/{release}/{version}/{arch}/{type}/packages/telephony

{extra_repositories}

## This is the local package repository, do not remove!
src imagebuilder file:packages
    """.strip().format(release=device.release, version=device.version, arch=device.arch, type=device.type, extra_repositories=extra_repositories)

    with open(os.path.join(intermediates_device_dir, IMAGE_BUILDER_DIR_NAME, "repositories.conf"), "w") as f:
      f.write(default_repo)

  def _prompt_for_build_confirmation(self):
    print("building for the following devices, please confirm: ")
    for name, device in self._devices.iteritems():
      print("  - {} at {} ({})".format(device.device_name, name, device.device_type))

    print("")
    raw_input("Press enter to continue, CTRL+C to abort ")
