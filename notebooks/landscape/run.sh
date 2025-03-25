#!/bin/bash

set -x

for file in */*-landscape.ipynb; do
    # you can add --debug to this command to get all of the output
    python -m nbconvert --execute --to notebook --output $(basename $file) $file
done
