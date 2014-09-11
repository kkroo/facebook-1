from . import WebCommonBase 
import requests

class Sender:
    def send_msg(self, recipient, sender, body):
        raise NotImplementedError

class APISender(WebCommonBase):
    def __init__(self, db, config, log):
      WebCommonBase.__init__(self)
      self.config = config
      self.db = db
      self.log = log

    def send_msg(self, imsi, sender, body):
        # Fetch the destination IMSI and the BTS it lives on
        accounts = self.db.select([self.config.t_users, self.config.t_base_stations], \
            where="imsi=$imsi " + \
              "AND %s.bts_key = %s.key" % (self.config.t_users, self.config.t_base_stations), \
            vars={"imsi": imsi})
        account = accounts[0]

        if not account:
          self.log.error("Message send failed. Account %s doesn't exist" % imsi)
          raise Exception("Message send failed. Account %s doesn't exist" % imsi)


        self.log.info("Sending incoming message to base station: from=%s, body=%s, to=%s, base_station=%s, url=%s" % \
            (sender, body, imsi, account.bts_key, account.callback_url))
        params = {'imsi': account.imsi, 'sender_id': sender.facebook_id, 'sender_name': sender.name, 'body': body}
        params['mac'] = WebCommonBase.compute_mac(params, self.config.key)
        r = requests.post(account.callback_url + "/callback", params, verify=False) # XXX THIS IS INSECURE!!!


