"""
The {{configuration.name }} assembles semantic mappings to the following
resources:

{{ table }}

Results
*******
The {{configuration.name }} is available for download as SSSOM, JSON, and
in a format ready for loading into a Neo4j graph database
on Zenodo at |{{ configuration.key }}img|.

A summary of the results can be viewed on the SeMRA GitHub repository in the
`notebooks/landscape/{{ configuration.key }} <https://github.com/biopragmatics/semra/tree/main/notebooks/landscape/{{ configuration.key }}#readme>`_
folder.

Reproduction
************

The {{configuration.name }} can be rebuilt with the following commands:

.. code-block:: console

    $ git clone https://github.com/biopragmatics/semra.git
    $ cd semra
    $ uv pip install .[landscape]
    $ python -m semra.landscape.{{ configuration.key }}

Web Application
***************

{%- if configuration.zenodo_record %}
The pre-built artifacts for this mapping database can be downloaded from Zenodo
at |{{ configuration.key }}img| and unzipped. The web application can be run
locally on Docker from inside the folder where the data was unzipped with:

.. code-block:: console

    $ sh run_on_docker.sh

If you reproduced the database yourself, you can ``cd``
to the right folder and run with:
{%- else %}
After building the database, the web application can be run locally on Docker
with the following commands:
{%- endif %}

.. code-block:: console

    $ cd ~/.data/semra/case-studies/{{ configuration.key }}
    $ sh run_on_docker.sh

Finally, navigate in your web browser to http://localhost:8773 to see the web
application.

.. |{{ configuration.key }}img| image:: https://zenodo.org/badge/DOI/10.5281/zenodo.{{ configuration.zenodo_record }}.svg
    :target: https://doi.org/10.5281/zenodo.{{ configuration.zenodo_record }}

"""  # noqa:D205,D400

