from setuptools import setup

setup(name="facebooksms",
      version="0.0.1",
      description="Facebook for SMS",
      author="Omar Ramadan",
      author_email="omar.ramadan@berkeley.edu",
      license='bsd',
      packages=['facebooksms'],
      install_requires=[
          'requests',
          'web.py',
          'pyyaml',
          'lxml',
          'cssselect',
          'pyyaml'
      ],
      dependency_links=['http://github.com/kkroo/SleekXMPP/tarball/master'],
      scripts=['facebooksms-interactive', 'web/facebooksms-client.py'],
      data_files=[
                      ('/var/log/facebooksms', []),
                      ('/etc/facebooksms/', ['conf/client.yaml']),
                      ('/etc/lighttpd/conf-enabled/', ['web/10-facebooksms-client-fastcgi.conf']),
                      ('/usr/share/freeswitch/scripts/', \
                          ['freeswitch/VBTS_FacebookSMS_Main.py', 'freeswitch/VBTS_FacebookSMS_Callback.py'])
                  ]
)
