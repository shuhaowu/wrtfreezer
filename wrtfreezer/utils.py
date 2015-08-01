from contextlib import contextmanager
import hashlib
import os
import os.path


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
