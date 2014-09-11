import sqlite3
from Crypto.PublicKey import RSA

class BaseConfig(object):
  def __init__(self, config_dict, logger):
    self.config_dict = config_dict
    self.log = logger
    self._key = None

    if 'db_file' in self.config_dict:
        # verify safety of db table names
        self._scrub(self.config_dict['t_users'])

        self.db_conn = sqlite3.connect(self.db_file)
        self.log.debug("Connnected to DB: %s" % self.db_file)

  def _scrub(self, string):
    """ Make sure the string is alphanumeric. We do this to sanitize our
    table names (since DB-API parameter substitution doesn't work for table
    names). """
    if not string.isalnum():
      raise ValueError("Table name cannot include non-alphanumerics.")
    return string

  @property
  def ca_path(self):
    return self.config_dict['ca_path']

  @property
  def db_file(self):
    return self.config_dict['db_file']

  @property
  def log_dir(self):
    return self.config_dict['log_dir']

  @property
  def log_level(self):
    return self.config_dict['log_level']

  @property
  def cert_file(self):
    return self.config_dict['cert_file']

  @property
  def api_cert_file(self):
    return self.config_dict['api_cert_file']

  @property
  def key_file(self):
    return self.config_dict['key_file']

  @property
  def key(self):
    if not self._key:
      key_file = open(self.key_file, 'r')
      self._key = RSA.importKey(key_file.read())
      key_file.close()
    return self._key
