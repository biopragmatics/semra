# Landscape Analysis

This folder contains results from a workflow for automating the analysis of the
landscape of a given domain, given a declarative configuration describing the
resources in that domain. It includes five landscape analyses:

1. [Disease](disease/disease-landscape.ipynb)
2. [Cell & Cell Line](cell/cell-landscape.ipynb)
3. [Anatomy](anatomy/anatomy-landscape.ipynb)
4. [Protein Complex](complex/complex-landscape.ipynb)
5. [Gene](gene/gene-landscape.ipynb)

## Example

Below, we highlight the disease landscape. Each analysis creates a graph of the
processed mappings.

![](disease/graph.svg)

We're able to automatically generate an UpSet plot like the one in
[How many rare diseases are there? (Haendel _et al._, 2020)](https://doi.org/10.1038/d41573-019-00180-y)
(a similar plot to the following appears in the
[supplementary info](https://media.nature.com/original/magazine-assets/d41573-019-00180-y/17308594)
and an explanation appears on [zenodo](https://zenodo.org/records/3478576)).
Note that our plot is about all diseases, not specifically rare ones:

![](disease/landscape_upset.svg)

The following histogram estimates how many diseases there are. Importantly, it
shows how many show up in a single resource, how many show up in all resources,
and how many show up in a few

![](disease/landscape_histogram.svg)

## Summary

A summary chart over all landscapes can be generated with `landscape.py`.

| name    | raw_term_count | unique_term_count | reduction |                                                                download |
| ------- | -------------: | ----------------: | --------: | ----------------------------------------------------------------------: |
| disease |        410,173 |           243,730 |  0.405787 | [zenodo.record:11091886](https://bioregistry.io/zenodo.record:11091886) |
| anatomy |         37,917 |            32,108 |  0.153203 | [zenodo.record:11091803](https://bioregistry.io/zenodo.record:11091803) |
| complex |         15,869 |             7,775 |  0.510051 | [zenodo.record:11091422](https://bioregistry.io/zenodo.record:11091422) |
| gene    |     49,457,767 |           207,019 |  0.013529 | [zenodo.record:11092013](https://bioregistry.io/zenodo.record:11092013) |
| cell    |        207,019 |           166,274 |  0.196818 | [zenodo.record:11091581](https://bioregistry.io/zenodo.record:11091581) |


## Rebuild

Run all notebooks after installing semra with the `landscape-notebook` extra,
then running the following

```console
$ git clone https://github.com/biopragmatics/semra.git
$ cd semra
$ uv pip install .[landscape-notebooks]
$ sh run.sh
```
