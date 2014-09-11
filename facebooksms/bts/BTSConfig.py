import sqlite3
from . import *

class BTSConfig(BaseConfig):
  @property
  def t_users(self):
      return self._scrub(self.config_dict['t_users'])

  @property
  def t_base_stations(self):
      return self._scrub(self.config_dict['t_base_stations'])

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
