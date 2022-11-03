funcX - Fast Function Serving
=============================
|licence| |build-status| |docs| |launch| |NSF-2004894| |NSF-2004932|

funcX is a high-performance function-as-a-service (FaaS) platform that enables
intuitive, flexible, efficient, scalable, and performant remote function execution
on existing infrastructure including clouds, clusters, and supercomputers.

.. |licence| image:: https://img.shields.io/badge/License-Apache%202.0-blue.svg
   :target: https://github.com/funcx-faas/funcX/blob/master/LICENSE
   :alt: Apache Licence V2.0
.. |build-status| image:: https://travis-ci.com/funcx-faas/funcX.svg?branch=master
   :target: https://travis-ci.com/funcx-faas/funcX
   :alt: Build status
.. |docs| image:: https://readthedocs.org/projects/funcx/badge/?version=latest
   :target: https://funcx.readthedocs.io/en/latest/
   :alt: Documentation Status
.. |launch| image:: https://mybinder.org/badge_logo.svg
   :target: https://mybinder.org/v2/gh/funcx-faas/examples/HEAD?filepath=notebooks%2FIntroduction.ipynb
   :alt: Launch in Binder
.. |NSF-2004894| image:: https://img.shields.io/badge/NSF-2004894-blue.svg
   :target: https://nsf.gov/awardsearch/showAward?AWD_ID=2004894
   :alt: NSF award info
.. |NSF-2004932| image:: https://img.shields.io/badge/NSF-2004932-blue.svg
   :target: https://nsf.gov/awardsearch/showAward?AWD_ID=2004932
   :alt: NSF award info


.. image:: docs/_static/logo.png
  :target: https://www.funcx.org
  :width: 200

Website: https://www.funcx.org

Documentation: https://funcx.readthedocs.io/en/latest/

Quickstart
==========

This fork of FuncX disables openssl verification of certificates in order to run on systems that intercept ssl traffic.

To install funcX, please ensure you have python3.6+.::

   $ python3 --version

Install using Pip::

   $ git clone https://github.com/illinois-ceesd/funcX-CEESD.git
   $ cd funcx-CEESD/funcx_sdk
   $ pip install .
   $ cd ../funcx_endpoint
   $ pip install .

This will also install the necessary version of Parsl.

To use our example notebooks you will need Jupyter.::

   $ pip install jupyter

.. note:: The funcX client is supported on MacOS, Linux and Windows.
          The funcx-endpoint is only supported on Linux.

Setting Up an Endpoint
----------------------
These instructions assume that you have funcX and Parsl installed (and loaded if using a conda environment).
You will also need a valid Globus login in order to start the endpoint.
The first step is to create a funcX endpoint::

   $ funcx-endpoint configure <ENDPOINT_NAME>

The `ENDPOINT_NAME` can be any name you want (no spaces though). You will likely need to copy and paste a globus
address into your browser. Follow the instructions on the web page to authenticate and paste the resulting code into
the terminal.

Depending on what machine you are running the endpoint on you may want to edit the default configuration (found in `~/.funcx/<ENDPOINT_NAME>/config.py`).
The configurations are Parsl Config objects (see below_ for details). If you are running on a standalone machine then
use either the default config or ThreadPoolExecutor. For Lassen or Quartz then either a generic HighThroughputExecutor
or one tuned to the machine should be used. Regardless of the configuration you will want to update the `meta` section at the bottom::

   meta = {
    "name": "<ENDPOINT_NAME>",
    "description": "",
    "organization": "",
    "department": "",
    "public": False,
    "visible_to": [],
   }
The description, organization, and department are optional; public will generally be False (True means anyone can use the endpoint);
In the `visible_to` list put an entry for each of the globus users (including yourself) in the following form::

    'urn:globus:auth:identity:<GLOBUS_USER_UUID>'

This will allow only those users to access the endpoint remotely.

Start the endpoint
------------------
To start the endpoint just run::

   $ funcx-endpoint start <ENDPOINT_NAME>

You will get some warnings about ssl security, these can be ignored. The command will also print out a line like::

   Starting endpoint with uuid: <UUID>

Save this for later as you will need it to connect to the endpoint remotely. This endpoint will always use this identifier.

Check that the endpoint is running properly::

   funcx-endpoint list

This will return a list of your enpoints on this machine, their status, and UUID (in case you missed it from before). The status should be `Running`.

.. _below:
Parsl
-----
The best resource for learning about Parsl is the `Parsl documentation<https://parsl.readthedocs.io/en/stable/>`_.
Below are configs that have worked on Lassen and Quartz. While they do work, they are not optimized for every job.
Specifically, options for the number of nodes, tasks per node, cores and memory per node, scheduler_options, and
worker_init may need to be tuned depending on job requirements.

Quartz config::

  qtz_htex = HighThroughputExecutor(label="quartz_htex",     # label is for internal reference for the user
                                    working_dir=QUARTZ_workdir,  # the working directory you want to use
                                    address='quartz.llnl.gov',  # assumes Parsl is running on a login node
                                    worker_port_range=(50000, 55000),
                                    worker_debug=True,
                                    provider=SlurmProvider(
                                        launcher=SrunLauncher(overrides=f'-N 1 -n 1 -o {QUARTZ_workdir}/j$$.stdo -e {QUARTZ_workdir}/j$$.stde'),
                                        walltime="01:00:00",    # expected max run time
                                        nodes_per_block=1,
                                        init_blocks=1,
                                        max_blocks=1,
                                        scheduler_options='#SBATCH -p pdebug',
                                        worker_init=(           # these are run in the shell before your code is executed
                                            'module load gcc/7.3.0\n'
                                            'module load openmpi/4.1.0\n'
                                            f'source {QUARTZ_CONDA_ENV}\n'
                                            'export XDG_CACHE_HOME="/tmp/$USER/xdg-scratch"\n'
                                        ),
                                        cmd_timeout=600
                                    ))
  config = Config(executors=[qtz_htex],
                  internal_tasks_max_threads=2,
                  strategy=None
                  )

Lassen config::

  lassen_htex = HighThroughputExecutor(label="lassen_htex",     # label is for internal reference for the user
                                       working_dir=LASSEN_workdir,  # the working directory you want to use
                                       address='lassen.llnl.gov',  # assumes Parsl is running on a login node
                                       worker_port_range=(50000, 55000),
                                       worker_debug=True,
                                       provider=LSFProvider(
                                           launcher=JsrunLauncher(
                                               overrides=f'-g 1 -a 1 -o {LASSEN_workdir}/j$$.stdo -k {LASSEN_workdir}/j$$.stde'),
                                           walltime="01:00:00",    # expected max run time
                                           nodes_per_block=1,
                                           init_blocks=1,
                                           max_blocks=1,
                                           bsub_redirection=True,
                                           scheduler_options='#BSUB -q pdebug',
                                           worker_init=(          # these are run in the shell before your code is executed
                                               'module load gcc/7.3.1\n'
                                               'module load spectrum-mpi\n'
                                               'export XDG_CACHE_HOME="/tmp/$USER/xdg-scratch"\n'
                                           ),
                                           project='uiuc',
                                           cmd_timeout=600
                                       ),
                                       )
  config = Config(executors=[lassen_htex],
                  strategy=None
                  )

Documentation
=============

Complete documentation for funcX is available `here <https://funcx.readthedocs.io>`_

