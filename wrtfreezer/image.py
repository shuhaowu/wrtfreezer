from __future__ import absolute_import, print_function

import logging
import os
import os.path
import subprocess
import shutil

import requests

from .utils import cd, md5_file

logging_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s: %(message)s")

CHUNK_SIZE = 1024 * 1024  # 1MB
BUILDER_FILENAME = "imagebuilder.tar.bz2"


class Image(object):
  def __init__(self, work_directory, config):
    self.work_directory = work_directory
    self.config = config
    self.release = config["release"]
    self.version = config["version"]
    self.arch = config["arch"]
    self.type = config["type"]

    self.logger = logging.getLogger("{}_{}_{}_{}".format(self.release, self.version, self.arch, self.type))
    handler = logging.StreamHandler()
    handler.setFormatter(logging_formatter)
    self.logger.addHandler(handler)
    self.logger.setLevel(logging.DEBUG)

    self.target_directory = os.path.join(
      self.work_directory,
      self.release,
      self.version,
      self.arch,
      self.type
    )

  def _setup_directory(self):
    release_dir = os.path.join(self.work_directory, self.release)
    if not os.path.exists(release_dir):
      os.mkdir(release_dir, 0755)

    version_dir = os.path.join(release_dir, self.version)
    if not os.path.exists(version_dir):
      os.mkdir(version_dir, 0755)

    arch_dir = os.path.join(version_dir, self.arch)
    if not os.path.exists(arch_dir):
      os.mkdir(arch_dir, 0755)

    type_dir = os.path.join(arch_dir, self.type)
    if not os.path.exists(type_dir):
      os.mkdir(type_dir, 0755)

  def _download_builder(self):
    """Download the image builder and verify hash

    This function essentially does: wget https://downloads.openwrt.org/barrier_breaker/14.07/ar71xx/generic/OpenWrt-ImageBuilder-ar71xx_generic-for-linux-x86_64.tar.bz2

    Returns:
      if an image was downloaded or not.
    """

    filename = "OpenWrt-ImageBuilder-{}_{}-for-linux-x86_64.tar.bz2".format(self.arch, self.type)
    filename_fallback = "OpenWrt-ImageBuilder-{}-for-linux-x86_64.tar.bz2".format(self.arch)

    self.logger.info("checking if image generator is up to date")
    r = requests.get("https://downloads.openwrt.org/{}/{}/{}/{}/md5sums".format(self.release, self.version, self.arch, self.type))
    if r.status_code != 200:
      raise RuntimeError("cannot get md5sums from openwrt...")

    md5sums = filter(lambda l: filename in l or filename_fallback in l, r.text.strip().split("\n"))
    md5sums = [line.split(" ")[0].strip() for line in md5sums]

    # make sure that the file doesn't already exists...
    builder_filename = os.path.join(self.target_directory, BUILDER_FILENAME)
    if os.path.exists(builder_filename):
      if md5_file(builder_filename) in md5sums:
        self.logger.info("image generator is up to date, skipping download")
        return False

    url_primary = "https://downloads.openwrt.org/{}/{}/{}/{}/{}".format(self.release, self.version, self.arch, self.type, filename)
    url_fallback = "https://downloads.openwrt.org/{}/{}/{}/{}/".format(self.release, self.version, self.arch, self.type, filename_fallback)

    self.logger.info("downloading image generator...")
    r = requests.get(url_primary)
    if r.status_code == 404:
      r = requests.get(url_fallback)
      if r.status_code == 404:
        raise ValueError("cannot find image builder for {}/{}/{}/{}".format(self.release, self.version, self.arch, self.type))

    with open(os.path.join(self.target_directory, BUILDER_FILENAME), "wb") as f:
      count = 0
      for chunk in r.iter_content(CHUNK_SIZE):
        f.write(chunk)
        count += 1
        if count % 5 == 0:
          self.logger.debug("{}MB downloaded...".format(count))

    self.logger.info("image generator downloaded, verifying...")
    downloaded_md5 = md5_file(builder_filename)
    if downloaded_md5 not in md5sums:
      raise RuntimeError("validation of download failed: expected {}, got {}".format(md5sums, downloaded_md5))

    self.logger.info("image generator verified, untarring...")
    with cd(self.target_directory):
      subprocess.check_call(["tar", "-xjf", BUILDER_FILENAME])

      for path in os.listdir("."):
        if path.startswith("OpenWrt-ImageBuilder") and os.path.isdir(path):
          shutil.move(path, "imagebuilder")
          break

    return True

  def _setup_repositories_conf(self):
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
    """.strip().format(release=self.release, version=self.version, arch=self.arch, type=self.type, extra_repositories=extra_repositories)

    with open(os.path.join(self.target_directory, "imagebuilder", "repositories.conf"), "w") as f:
      f.write(default_repo)

  def setup(self):
    self.logger.info("setting up image generator...")
    self._setup_directory()
    self._download_builder()
    self._setup_repositories_conf()
    self.logger.info("setup complete!")

  def build_one(self, profile, data):
    self.logger.info("starting to build for {}".format(profile))
    with cd(os.path.join(self.target_directory, "imagebuilder")):
      cmd = ["make", "image", "PROFILE={}".format(profile)]

      packages = data.get("packages")
      if packages:
        cmd.append('PACKAGES={}'.format(" ".join(data["packages"])))

      files_directory = data.get("files_directory")
      if files_directory:
        cmd.append("FILES={}".format(files_directory))

      subprocess.check_call(cmd)

  def build(self):
    for profile, data in self.config["profiles"].iteritems():
      self.build_one(profile, data)

  def clean(self):
    self.logger.info("running make clean...")
    with cd(os.path.join(self.target_directory, "imagebuilder")):
      subprocess.check_call(["make", "clean"])
