import os
 
from distutils.core import setup
 
def fullsplit(path, result=None):
    """
    Split a pathname into components (the opposite of os.path.join) in a
    platform-neutral way.
    """
    if result is None:
        result = []
    head, tail = os.path.split(path)
    if head == "":
        return [tail] + result
    if head == path:
        return result
    return fullsplit(head, [tail] + result)
 
package_dir = "googlecharts"
 
packages = []
for dirpath, dirnames, filenames in os.walk(package_dir):
    # ignore dirnames that start with '.'
    for i, dirname in enumerate(dirnames):
        if dirname.startswith("."):
            del dirnames[i]
    if "__init__.py" in filenames:
        packages.append(".".join(fullsplit(dirpath)))
 
setup(
    name = 'django-googlecharts',
    version = '0.1.0',
    description = 'django-googlecharts provides template tags to easily be able to insert '
                  'charts using the google api in your pages.',
    keywords = 'django apps',
    license = 'see License',
    author = 'Jacob Kaplan-Moss',
    author_email = 'jacob@jacobian.org',
    maintainer = 'Rohit Sankaran',
    maintainer_email = 'rohit@lincolnloop.com',
    url = 'http://github.com/roadhead/django-googlechart/',
    dependency_links = [],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Plugins',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    packages = packages,
    include_package_data = True,
)