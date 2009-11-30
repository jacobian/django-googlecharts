"""
Test support harness for doing setup.py test.
See http://ericholscher.com/blog/2009/jun/29/enable-setuppy-test-your-django-apps/.
"""

import sys

# Configure settings
from django.conf import settings
settings.configure(
    DATABASE_ENGINE = 'sqlite3',
    INSTALLED_APPS = ['googlecharts'],
)

# setup.py test runner
from django.test.utils import get_runner

def runtests():
    test_runner = get_runner(settings)
    failures = test_runner(['googlecharts'], verbosity=1, interactive=True)
    sys.exit(failures)