class Message:
  def __init__(self, sender, recipient, subject, body):
    self.sender = sender
    self.recipient = recipient
    self.subject = subject
    self.body = body

  def is_valid(self):
    return self.sender and self.recipient and self.body

  def __str__(self):
    return "from='%s', to='%s', subject='%s', body='%s'" % (self.sender,
                                              self.recipient,
                                              self.subject,
                                              self.body)
