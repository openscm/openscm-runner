.. _settings-reference:

Settings API
------------

.. automodule:: openscm_runner.settings


Available Settings
------------------

MAGICC settings
~~~~~~~~~~~~~~~

MAGICC_EXECUTABLE_7
+++++++++++++++++++

Path to the compiled MAGICC executable.

The assumption is made that your MAGICC directory structure looks like
this:

.. code::

    . top-level-dir
    ├── bin
    │ └── magicc
    ├── out  # empty folder where output can be written
    └── run
      ├── run files are here
      └── they shouldn't need to be touched directly


MAGICC_WORKER_NUMBER
++++++++++++++++++++

Default: `Number of CPU cores in system` (``os.cpu_count()``)

How many MAGICC workers should be run in parallel?

MAGICC_WORKER_ROOT_DIR
++++++++++++++++++++++

Where should the MAGICC workers be located on the filesystem (you need about
500Mb space per worker at the moment)
