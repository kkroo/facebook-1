import sqlite3

class Config:
  def __init__(self, config_dict, logger):
    self.config_dict = config_dict
    self.log = logger

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
  def t_users(self):
      return self._scrub(self.config_dict['t_users'])

  @property
  def db_file(self):
    return self.config_dict['db_file']

  @property
  def app_number(self):
    return self.config_dict['app_number']

  @property
  def number_prefix(self):
    return self.config_dict['number_prefix']

  @property
  def sender_type(self):
    return self.config_dict['sender_type']

  @property
  def provider_type(self):
    return self.config_dict['provider_type']


