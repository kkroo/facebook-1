import logging

class Sender:
    def send_sms(self, sender, recipient, subject, data):
        raise NotImplementedError

class TestSender(Sender):
    """ Saves output to an easily parse-able file format to allow automated
    verification.
    """

    def __init__(self):
        self.msg_count = 0
        self.logger = logging.getLogger("testsender")
    def send_sms(self, sender, recipient, subject, data):
        msg = [ self.msg_count, sender, recipient, subject, data ]
        self.logger.info("%s" % msg)
        print "%s" % msg
        self.msg_count += 1


class LogSender(Sender):
    def send_sms(self, sender, recipient, subject, data):
        logging.basicConfig(level=logging.DEBUG)
        logging.info("Sent SMS. From: '%s' To: '%s' Subj: '%s' Message: '%s'" \
                     % (sender, recipient, subject, data))
        return True

class FreeSwitchSender(Sender):
    def __init__(self):
      from libvbts import FreeSwitchMessenger

    def send_sms(self, sender, recipient, subject, data):
        sender = str(sender)
        subject = '' if subject is None else "%s: " % subject
        consoleLog('info', str("sending '%s' to %s from %s\n" % (data, recipient, sender)))
        fs = FreeSwitchMessenger.FreeSwitchMessenger()
        fs.send_smqueue_sms("", recipient, sender, subject + data)

class ESLSender(Sender):
    def __init__(self):
      from vbts_interconnects import vbts_util
      from ESL import ESLconnection

    def send_sms(self, sender, recipient, subject, body):
      conf = vbts_util.get_conf_dict()
      esl = ESLconnection(conf['fs_esl_ip'], conf['fs_esl_port'], conf['fs_esl_pass'])
      if esl.connected():
         e = esl.api("python VBTS_FacebookSMS_Callback %s|%s|%s|%s" %\
             (sender, recipient, subject, body))
      else:
         raise Exception("Freeswitch is not running")

