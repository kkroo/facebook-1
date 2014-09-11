#!/usr/bin/env python
import threading
import traceback
import logging, yaml
import web, requests
import syslog
import re
from facebooksms.bts import *

urls = ("/callback", "callback", \
        "/activate", "activate")

class BTSWebBase(WebCommonBase):
    def __init__(self):
        WebCommonBase.__init__(self)
        conf_file = open("/etc/facebooksms/client.yaml", "r")
        config_dict = yaml.load("".join(conf_file.readlines()))
        config_dict['sender_type'] = 'esl'
        conf = BTSConfig(config_dict, web.log)
        self.app = FacebookSMS(conf)
        r = web.db.select(self.config.t_users, where="imsi=$imsi", vars={'imsi': self.data.imsi})
        try:
          account = r[0]
        except Exception:
          raise web.Unauthorized()

        self.app.user = User(self.app, account.number)
        self.app.msg = Message(account.number, self.config.app_number, None, None, self.data.imsi)

class callback(BTSWebBase):
    def POST(self):
        self.fields_to_verify += ["sender_id", "sender_name", "body"]
        web.log.debug("Incoming callback %s" % self.data)
        web.log.info("Sending msg to freeswitch for sender=%s, recipient=%s" % (self.data.sender_id, self.data.imsi))
        sender = FacebookUser(self.data.sender_id, self.data.sender_name)
        msg = Post(sender, self.data.imsi, self.data.body)
        self.app.handle_incoming_message(msg)
        raise web.Accepted()

class activate(BTSWebBase):
    def POST(self):
        web.log.debug("Incoming activation %s" % self.data)
        self.app.set_user_active(True)
        raise web.Accepted()

if __name__ == "__main__":
    web.config.debug = True

    web.log = logging.getLogger("facebooksms.client")
    conf_file = open("/etc/facebooksms/client.yaml", "r")
    config_dict = yaml.load("".join(conf_file.readlines()))
    web.fb_config = BTSConfig(config_dict, web.log )
    logging.basicConfig(filename="%s/client.log" % web.fb_config.log_dir, level=web.fb_config.log_level)
    web.log.info("Starting up client.")
    web.db = web.database(dbn='sqlite', db=web.fb_config.db_file)
    app = web.application(urls, locals())
    app.run()
    web.log.info("Terminating client.")

