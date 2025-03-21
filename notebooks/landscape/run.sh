#!/bin/bash

set -x

for file in */*.ipynb; do
    # you can add --debug to this command to get all of the output
    jupyter nbconvert --execute --to notebook --output $file $file
done
