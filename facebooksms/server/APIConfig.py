from . import BaseConfig

class APIConfig(BaseConfig):
  @property
  def t_users(self):
      return self._scrub(self.config_dict['t_users'])

  @property
  def t_base_stations(self):
      return self._scrub(self.config_dict['t_base_stations'])

  @property
  def fb_client_id(self):
    return self.config_dict['fb_client_id']

  @property
  def fb_client_secret(self):
    return self.config_dict['fb_client_secret']

  @property
  def enable_registration(self):
    return self.config_dict['enable_registration']

  @property
  def server_url(self):
    return self.config_dict['server_url']

