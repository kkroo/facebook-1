class Message:
  def __init__(self, sender, recipient, subject, body, imsi=None):
    self.sender = sender
    self.recipient = recipient
    self.subject = subject
    self.body = body
    self.imsi = imsi

  def is_valid(self):
    return self.sender and self.recipient and self.body

  def __str__(self):
    return "from='%s', to='%s', subject='%s', body='%s', imsi='%s'" % (self.sender,
                                              self.recipient,
                                              self.subject,
                                              self.body,
                                              self.imsi)
