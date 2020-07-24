import os
from distutils.core import setup

packages = []
for root, dirs, files in os.walk("memento_damage"):
    if '__init__.py' in files:
        packages.append(root)

packages.reverse()

packages_non_package_dirs = {}
for root, dirs, files in os.walk("memento_damage"):
    for package in packages:
        if root == package:
            non_package_dirs = []
            for dir in dirs:
                fullpath_dir = os.path.join(root, dir)
                if fullpath_dir not in packages:
                    non_package_dirs.append(dir)

            packages_non_package_dirs[package] = non_package_dirs

packages_data = {}
for package, non_package_dirs in packages_non_package_dirs.items():
    packages_data.setdefault(package, [])
    for non_package_dir in non_package_dirs:
        fullpath_non_package_dir = os.path.join(package, non_package_dir)

        for root, dirs, files in os.walk(fullpath_non_package_dir):
            if len(files) > 0:
                packages_data[package] += [os.path.join(root, f) for f in files]

packages = []
package_dir = {}
package_data = {}
for package, data in packages_data.items():
    packages.append(package.replace('/', '.'))
    package_dir[package.replace('/', '.')] = package

    data = [d.replace(package + '/', '') for d in data]
    package_data[package.replace('/', '.')] = data


setup(
    name='memento-damage',
    version='2.0.7',
    packages=packages,
    package_dir=package_dir,
    package_data=package_data,
    scripts=['memento_damage/cli/memento-damage', 'memento_damage/cli/memento-damage-server'],
    install_requires=[
        'pillow',
        'html2text',
        'flask',
        'Flask-SQLAlchemy'
    ],
    url='https://github.com/oduwsdl/web-memento-damage',
    license='',
    author='erikaris',
    author_email='erikaris1515@gmail.com',
    description='A tool for calculating damage of webpage'
)
