from distribute_setup import use_setuptools; use_setuptools()
from setuptools import setup, find_packages

setup(
    name = 'django-googlecharts',
    version = '1.0-alpha-1',
    description = 'Django template tags to generate charts using the Google chart API.',
    long_description = open("README").read(),
    keywords = 'django charts templates',
    license = 'BSD',
    author = 'Jacob Kaplan-Moss',
    author_email = 'jacob@jacobian.org',
    url = 'http://github.com/jacobian/django-googlecharts',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Plugins',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    packages = find_packages(),
    install_requires = ['Django>=1.0'],
    test_suite = "googlecharts.runtests.runtests",
)