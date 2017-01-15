from distutils.core import setup

setup(
    name='memento-damage',
    version='2.0',
    packages=['memento_damage'],
    package_dir={'memento_damage': 'memento_damage'},
    package_data={'memento_damage': ['cli/*', 'phantomjs/*']},
    scripts=['memento_damage/cli/memento-damage'],
    install_requires=[
        'pillow',
        'html2text',
        'flask',
        'Flask-SQLAlchemy'
    ],
    url='https://github.com/erikaris/web-memento-damage',
    license='',
    author='erikaris',
    author_email='erikaris1515@gmail.com',
    description='A tool for calculating damage of webpage'
)
