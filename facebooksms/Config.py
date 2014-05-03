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
  def t_base_stations(self):
      return self._scrub(self.config_dict['t_base_stations'])

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

  @property
  def api_key(self):
    return self.config_dict['api_key']

  @property
  def api_url(self):
    return self.config_dict['api_url']

  @property
  def callback_protocol(self):
    return self.config_dict['callback_protocol']

  @property
  def callback_port(self):
    return self.config_dict['callback_port']

  @property
  def callback_path(self):
    return self.config_dict['callback_path']

  @property
  def ca_path(self):
    return self.config_dict['ca_path']

  @property
  def cert_file(self):
    return self.config_dict['cert_file']

  @property
  def api_cert_file(self):
    return self.config_dict['cert_file']

  @property
  def key_file(self):
    return self.config_dict['key_file']

  @property
  def key(self):
    return self.config_dict['key']


