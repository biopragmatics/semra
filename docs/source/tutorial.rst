Usage
=====

1. I/O
2. How to make a configuration and run it
3. How to apply results

Data Science Tutorial
---------------------

SeMRA provides tools for data scientists to standardize references using semantic
mappings.

For example, the drug indications table in ChEMBL contains a variety of references to
EFO, MONDO, DOID, and other controlled vocabularies (described in detail in `this blog
post <https://cthoyt.com/2025/04/17/chembl-indications-efo-exploration.html>`_). Using
SeMRA's pre-constructed `disease and phenotype prioritization mapping
<https://doi.org/10.5281/zenodo.11091885>`_, these references can be standardized in a
deterministic and principled way.

.. code-block:: python

    import chembl_downloader
    import semra.io
    from semra.api import prioritize_df

    # A dataframe of indication-disease pairs, where the
    # "efo_id" column is actually an arbitrary disease or phenotype query
    df = chembl_downloader.query("SELECT DISTINCT drugind_id, efo_id FROM DRUG_INDICATION")

    # a pre-calculated prioritization of diseases and phenotypes from MONDO, DOID,
    # HPO, ICD, GARD, and more.
    url = "https://zenodo.org/records/15164180/files/priority.sssom.tsv?download=1"
    mappings = semra.io.from_sssom(url)

    # the dataframe will now have a new column with standardized references
    prioritize_df(mappings, df, column="efo_id", target_column="priority_indication_curie")
