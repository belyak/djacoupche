from setuptools import setup

setup(
    name='djacoupche',
    version='0.14',
    description='Django applications coupling checker (within concrete project)',
    url='http://github.com/belyak/djacoupche',
    author='Andrey Belyak',
    author_email='beliak@mail.ru',
    license='LGPLv3',
    packages=['djacoupche'],
    scripts=['bin/djacoupche'],
    zip_safe=False
)
