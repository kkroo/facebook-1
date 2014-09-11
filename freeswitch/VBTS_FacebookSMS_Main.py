#!/usr/bin/python
import logging
import sys
import re
import time
from facebooksms.bts import *
import yaml

def chat(message, args):
    args = args.split('|')
    if (len(args) < 4):
        consoleLog('err', 'Missing Args\n')
        exit(1)
    imsi = args[0]
    to = args[1]
    fromm = args[2]
    text = args[3]
    if ((not to or to == '') or
        (not fromm or fromm == '')):
        consoleLog('err', 'Malformed Args\n')
        exit(1)


    facebooksms_log = logging.getLogger("facebooksms.client")
    conf_file = open("/etc/facebooksms/client.yaml", "r")
    config_dict = yaml.load("".join(conf_file.readlines()))
    conf = BTSConfig(config_dict, facebooksms_log)
    logging.basicConfig(filename="%s/client.log" % conf.log_dir, level=conf.log_level)


    app = FacebookSMS(conf)

    consoleLog('info', "Got '%s' from %s(%s) to %s\n" % (text, fromm, imsi, to))
    facebooksms_log.info("Got '%s' from %s(%s) to %s" % (text, fromm, imsi, to))
    msg = Message(fromm, to, None, text, imsi)
    app.handle_incoming_sms(msg)

def fsapi(session, stream, env, args):
    #chat doesn't use message anyhow
    chat(None, args)


""" Chat plan """
"""
    <extension name="facebooksms">
      <condition field="vbts_tp_dest_address" expression="^999\d+$">
        <action application="python" data="VBTS_FacebookSMS_Main ${from_user}|${vbts_tp_dest_address}|${vbts_callerid}|${vbts_text}"/>
        <action application="set" data="response_text=${_openbts_ret}" />
      </condition>
    </extension>
"""
