AutoRemovePlus
==============

AutoRemovePlus is a plugin for [Deluge v1.x](http://deluge-torrent.org) that
you can use to automatically remove torrents. It's
based on AutoRemove 0.1 by Jamie Lennox.

For Deluge v2 support, see [this version](https://github.com/springjools/deluge-autoremoveplus)

This is a GtkUI and WebUI plugin.

Features
--------
- Select how many torrents are allowed at the same time.
- Choose to remove or pause them based on multiple criteria age, seeders, seed time or ratio.
- Set specific removal rules depending on tracker or LabelPlus label.
- Remove only torrents from specific trackers or LabelPlus labels.
- Only remove torrents if under a certain HDD space threshold.
- Select if torrents have to fulfill both or either criteria.
- Delete torrents in order (e.g. delete torrents with highest ratio first).
- Don't remove torrents if they don't reach a minimum time (in days) or ratio.
- Choose the removal interval.
- Right click and select torrents that you don't want automatically removed.
- Remove torrent data option.
- Create an exempted tracker or LabelPlus label list, so that torrents that belong to those trackers or labels are not removed.
- Fully functional WebUI.  

Usage
-----
Look for torrents to remove every hour:

> Check every: 1

Remove every torrent that meets minimum criteria:

> Maximum torrents: 0

Don't remove torrents unless Deluge has over 500:

> Maximum torrents: 500

Delete torrents even if HDD space not under minimum:

> Minimum HDD space: -1

Only remove torrents when the main HDD has less than 10 GB free:

> Minimum HDD space: 10

Remove torrents that have a ratio over 2.0 and have been seeding for at least 2 days:

> Remove by: Ratio, Min: 2.0, and, Remove by: Seed Time, Min: 48

Remove torrents that have a ratio over 2.0 or have been seeding for at least 10 hours:

> Remove by: Ratio, Min: 2.0, or, Remove by: Seed Time, Min: 10

Remove torrents that have a ratio over 2.2 and were added at least 4 days ago:

> Remove by: Ratio, Min: 2.2, or, Remove by: Age in days, Min: 4

Remove torrents only according to first criteria:

> :black_small_square: Second Remove by: criteria

Pause torrents instead of removing them:

> :black_small_square: Remove torrents

The rest of the options are pretty self explanatory

Development
-----------
- use python 2.7, as this version of plugin doesn't support Deluge 2 that runs on py3
- virutal env manager `virtualenv`
- run:

```
+ Install python 2
- py2 is likely unsupported on your distro, so first install pyenv:
  $ curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash
- install latest py2:  $ pyenv install 2.7.18
- cd to project root and change to version:  $ pyenv local 2.7.18
  - this will create .python-version file at the root
- verify your py version: $ python --version

+ Setup virtenv; either
A) manually... (not recommended):
- install virtualenv:  $ pip install virtualenv
- create venv:  $ python -m virtualenv env  (note 'env' specifies the name/location to create
  the virtual environment in)
- activate env:  $ source env/bin/activate
- to switch projects or just leave the venv, run:  $ deactivate
B) ...or using pyenv (recommended):
- this step might still be needed, unsure:  install virtualenv:  $ pip install virtualenv
- create venv:  $ pyenv virtualenv venv27  (again, 'venv27' is just the name/location)
- if you have [eval "$(pyenv virtualenv-init -)"] in your .bashrc, then
  env activation/deactivation should be automatic; to do it manually, then
    pyenv activate <name>
    pyenv deactivate

+ building project: see below
```

Building
--------

Run:

```
python setup.py bdist_egg
```

The resulting `AutoRemovePlus-x-py2.x.egg` file can be found in the `/dist` directory.

Workarounds
-----------

If after building the egg file, the plugin does not load in Deluge:

- Delete the `AutoRemovePlus-x-py2.x.egg` in `/deluge/plugins` directory.
- Delete the `AutoRemovePlus.conf` files.
- Restart Deluge.
