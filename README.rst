OpenSCM Runner
==============

+-------------------+----------------+--------+
| Repository health |    |CI CD|     | |Docs| |
+-------------------+----------------+--------+

+------+------------------+----------------+------------------+
| Pypi |  |PyPI Install|  |     |PyPI|     |  |PyPI Version|  |
+------+------------------+----------------+------------------+

+-------+-----------------+-------------------+-----------------+
| Conda | |conda install| | |conda platforms| | |conda version| |
+-------+-----------------+-------------------+-----------------+

+-----------------+----------------+---------------+-----------+
|   Other info    | |Contributors| | |Last Commit| | |License| |
+-----------------+----------------+---------------+-----------+

.. sec-begin-links

.. |CI CD| image:: https://github.com/openscm/openscm-runner/workflows/OpenSCM-Runner%20CI-CD/badge.svg
    :target: https://github.com/openscm/openscm-runner/actions?query=workflow%3A%22OpenSCM-Runner+CI-CD%22
.. |Docs| image:: https://readthedocs.org/projects/openscm-runner/badge/?version=latest
    :target: https://openscm-runner.readthedocs.io/en/latest/?badge=latest
.. |PyPI Install| image:: https://github.com/openscm/openscm-runner/workflows/Test%20PyPI%20install/badge.svg
    :target: https://github.com/openscm/openscm-runner/actions?query=workflow%3A%22Test+PyPI+install%22
.. |PyPI| image:: https://img.shields.io/pypi/pyversions/openscm-runner.svg
    :target: https://pypi.org/project/openscm-runner/
.. |PyPI Version| image:: https://img.shields.io/pypi/v/openscm-runner.svg
    :target: https://pypi.org/project/openscm-runner/
.. |conda install| image:: https://github.com/openscm/openscm-runner/workflows/Test%20conda%20install/badge.svg
    :target: https://github.com/openscm/openscm-runner/actions?query=workflow%3A%22Test+conda+install%22
.. |conda platforms| image:: https://img.shields.io/conda/pn/conda-forge/openscm-runner.svg
    :target: https://anaconda.org/conda-forge/openscm-runner
.. |conda version| image:: https://img.shields.io/conda/vn/conda-forge/openscm-runner.svg
    :target: https://anaconda.org/conda-forge/openscm-runner
.. |Contributors| image:: https://img.shields.io/github/contributors/openscm/openscm-runner.svg
    :target: https://github.com/openscm/openscm-runner/graphs/contributors
.. |Last Commit| image:: https://img.shields.io/github/last-commit/openscm/openscm-runner.svg
    :target: https://github.com/openscm/openscm-runner/commits/master
.. |License| image:: https://img.shields.io/github/license/openscm/openscm-runner.svg
    :target: https://github.com/openscm/openscm-runner/blob/master/LICENSE

.. sec-end-links


Brief summary
+++++++++++++

.. sec-begin-long-description
.. sec-begin-index

OpenSCM-Runner is a thin wrapper to run simple climate models with a unified interface.
At present, it supports emissions driven runs only.
This wrapper is implemented whilst `OpenSCM <https://github.com/openscm/openscm>`_ is still a work in progress.

.. sec-end-index

License
-------

.. sec-begin-license

OpenSCM-Runner is free software under a BSD 3-Clause License, see
`LICENSE <https://github.com/openscm/openscm-runner/blob/master/LICENSE>`_.

.. sec-end-license
.. sec-end-long-description

.. sec-begin-installation

Installation
------------

OpenSCM-Runner can be installed with conda

.. code:: bash

    conda install -c conda-forge openscm-runner

Note that the above only installs base dependencies. To install all the requirements for MAGICC, use the below

.. code:: bash

    # MAGICC
    conda install -c conda-forge openscm-runner pymagicc

To install all the requirements for FaIR, use the below

.. code:: bash

    # FaIR
    conda install -c conda-forge -c chrisroadmap openscm-runner fair

OpenSCM-Runner can also be installed with pip

.. code:: bash

    pip install openscm-runner

To install the dependencies required by all models known to OpenSCM-Runner, add additional dependencies using

.. code:: bash

    pip install openscm-runner[models]


To only install the dependencies required by a specific model, use one of the following instead

.. code:: bash

    # MAGICC
    pip install openscm-runner[magicc]
    # FaIR
    pip install openscm-runner[fair]

If you also want to run the example notebooks install additional
dependencies using

.. code:: bash

    pip install openscm-runner[notebooks]

.. sec-end-installation

Documentation
-------------

Documentation can be found at our `documentation pages <https://openscm-runner.readthedocs.io/en/latest/>`_
(we are thankful to `Read the Docs <https://readthedocs.org/>`_ for hosting us).

Contributing
------------

Please see the `Development section of the docs <https://openscm-runner.readthedocs.io/en/latest/development.html>`_.
