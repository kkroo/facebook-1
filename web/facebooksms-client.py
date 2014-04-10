#!/usr/bin/python
import threading
import traceback

import web, requests
import syslog
from vbts_interconnects import vbts_util
from ESL import *

urls = ("/callback", "callback")

class callback:
    def POST(self):
        data = web.input()
        needed_fields = ["imsi", "sender_id", "sender_name", "recipient", "body"]
        if all(i in data for i in needed_fields):
            imsi = str(data.imsi)
            sender_id = str(data.sender_id)
            sender_name = str(data.sender_name)
            recipient = str(data.recipient)
            body = str(data.body)
            self.send_to_fs(imsi, recipient, sender_id, sender_name, body)
            print data
            raise web.Accepted()
        raise web.BadRequest()

    def send_to_fs(self, imsi, recipient, sender_id, sender_name, body):
      conf = vbts_util.get_conf_dict()
      esl = ESLconnection(conf['fs_esl_ip'], conf['fs_esl_port'], conf['fs_esl_pass'])
      if esl.connected():
         e = esl.api("python VBTS_FacebookSMS_In %s|%s|%s|%s|%s" % (imsi, recipient, sender_id, sender_name, body))


if __name__ == "__main__":
    web.config.debug = True
    app = web.application(urls, locals())
    app.run()
