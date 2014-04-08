#!/usr/bin/python
from libvbts import FreeSwitchMessenger
from freeswitch import *
import logging
import sys
import re
import time
import facebooksms
import yaml

class FreeSwitchSender(facebooksms.Sender):

    def __init__(self, fbsms):
    	self.fbsms = fbsms

    def send_sms(self, sender, recipient, subject, data):
        sender = str(sender)
        subject = '' if subject is None else "%s: " % subject
        consoleLog('info', str("sending '%s' to %s from %s\n" % (data, recipient, sender)))
        self.fbsms.fs.send_smqueue_sms("", recipient, sender, subject + data)

def chat(message, args):
    logging.basicConfig(filename="/var/log/facebooksms.log", level="DEBUG")
    facebooksms_log = logging.getLogger("facebooksms.facebooksms")
    conf_file = open("/etc/facebooksms.yaml", "r")
    config_dict = yaml.load("".join(conf_file.readlines()))
    conf = facebooksms.Config(config_dict, facebooksms_log)

    app = facebooksms.FacebookSMS(conf)
    app.fs = FreeSwitchMessenger.FreeSwitchMessenger()
    fss = FreeSwitchSender(app)
    app.msg_sender = fss
    args = args.split('|')

    if (len(args) < 3):
        consoleLog('err', 'Missing Args\n')
        exit(1)
    to = args[0]
    fromm = args[1]
    text = args[2]
    if ((not to or to == '') or
        (not fromm or fromm == '')):
        consoleLog('err', 'Malformed Args\n')
        exit(1)

    consoleLog('info', "Got '%s' from %s to %s\n" % (text, fromm, to))
    msg = facebooksms.Message(fromm, to, None, text)
    app.handle_incoming(msg)

def fsapi(session, stream, env, args):
    #chat doesn't use message anyhow
    chat(None, args)


""" Chat plan """
"""
    <extension name="facebooksms">
      <condition field="vbts_tp_dest_address" expression="^999\d+$">
        <action application="python" data="VBTS_FacebookSMS ${vbts_tp_dest_address}|${openbts_callerid}|${vbts_text}"/>
        <action application="set" data="response_text=${_openbts_ret}" />
      </condition>
    </extension>
"""
