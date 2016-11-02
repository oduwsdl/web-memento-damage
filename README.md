==============
Memento Damage
==============

Memento Damage is a tool that help us to estimate damage of webpage.

Docker
======

Memento Damage can be used as docker container. There are two mode available, ``server`` and ``cli``. 

Server Mode
-----------

To use in ``server`` mode, use command below:

.. code-block:: bash

    docker pull erikaris/memento-damage:server
    
.. code-block:: bash

    docker run -i -t -p <local-port>:80 -v <local-path>:/app/cache --name <container-name> erikaris/memento-damage:server /bin/bash

Command Line Interface (CLI) Mode
---------------------------------

To use in ``cli`` mode, use command as below:

.. code-block:: bash

    docker pull erikaris/memento-damage:cli
    
.. code-block:: bash

    docker run -i -t -P -v <local-path>:/app/cache --name <container-name> erikaris/memento-damage:cli /bin/bash

To access terminal of ``cli``, use ``docker attach``.

.. code-block:: bash

    docker attach <container-name>
    
Then execute ``damage`` using command as below. If using ``csv`` input, put it first in ``<local-path>`` as defined in ``docker run`` above.

.. code-block:: bash

    damage <uri or csv>
    
The result will be appeared in both ``terminal`` and ``<local-path>/result.csv``.
