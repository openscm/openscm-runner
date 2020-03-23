OpenSCM Runner
==============

+----------------+-----------------+
| |CI CD|        | |PyPI Install|  |
+----------------+-----------------+
| |PyPI|         | |PyPI Version|  |
+----------------+-----------------+

Work in progress.

Brief summary
+++++++++++++

.. sec-begin-long-description
.. sec-begin-index

OpenSCM-Runner is a thin wrapper to run simple climate models with a unified interface.
It supports emissions driven runs only.
This wrapper is implemented whilst `OpenSCM <https://github.com/openclimatedata/openscm>`_ is still a work in progress.

.. sec-end-index

License
-------

.. sec-begin-license

OpenSCM-Runner is free software under a BSD 3-Clause License, see
`LICENSE <https://github.com/openscm-project/openscm-runner/blob/master/LICENSE>`_.

.. sec-end-license
.. sec-end-long-description

.. sec-begin-installation

Installation
------------

OpenSCM-Runner can be installed with pip

.. code:: bash

    pip install openscm-runner

If you also want to run the example notebooks install additional
dependencies using

.. code:: bash

    pip install openscm-runner[notebooks]

**Coming soon** OpenSCM-Runner can also be installed with conda

.. code:: bash

    conda install -c conda-forge openscm-runner

.. sec-end-installation

Documentation
-------------

Documentation can be found at our `documentation pages <https://openscm-runner.readthedocs.io/en/latest/>`_
(we are thankful to `Read the Docs <https://readthedocs.org/>`_ for hosting us).

Contributing
------------

Please see the `Development section of the docs <https://openscm-runner.readthedocs.io/en/latest/development.html>`_.

.. sec-begin-links

.. |CI CD| image:: https://github.com/openscm-project/openscm-runner/workflows/openscm-runner%20CI-CD/badge.svg
    :target: https://github.com/openscm-project/openscm-runner/actions?query=workflow%3A%22openscm-runner+CI-CD%22
.. |PyPI Install| image:: https://github.com/openscm-project/openscm-runner/workflows/Test%20PyPI%20install/badge.svg
    :target: https://github.com/openscm-project/openscm-runner/actions?query=workflow%3A%22Test+PyPI+install%22
.. |PyPI| image:: https://img.shields.io/pypi/pyversions/openscm-runner.svg
    :target: https://pypi.org/project/openscm-runner/
.. |PyPI Version| image:: https://img.shields.io/pypi/v/openscm-runner.svg
    :target: https://pypi.org/project/openscm-runner/

.. sec-end-links
