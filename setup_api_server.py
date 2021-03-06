from distutils.core import setup, Extension

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
          'Crypto'
      ],
      dependency_links=['http://github.com/kkroo/SleekXMPP/tarball/master'],
      scripts=['facebooksms-interactive', 'web/facebooksms-api-server.py'],
      data_files=[
                      ('/var/log/facebooksms', []),
                      ('/etc/facebooksms/', ['conf/api.yaml']),
                      ('/etc/lighttpd/conf-enabled/', ['web/10-facebooksms-api-server-fastcgi.conf']),
                  ]
)
