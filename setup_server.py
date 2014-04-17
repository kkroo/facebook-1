from distutils.core import setup, Extension

setup(name="facebooksms",
      version="0.0.1",
      description="Facebook for SMS",
      author="Omar Ramadan",
      author_email="omar.ramadan@berkeley.edu",
      license='bsd',
      packages=['facebooksms'],
      scripts=['facebooksms-interactive', 'web/facebooksms-server.py'],
      data_files=[
                      ('/var/log/facebooksms', []),
                      ('/etc/facebooksms/', ['conf/server.yaml']),
                      ('/etc/lighttpd/conf-enabled/', ['web/10-facebooksms-server-fastcgi.conf']),
                  ]
)
