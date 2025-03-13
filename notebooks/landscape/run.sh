#!/bin/bash

for file in */*.ipynb; do
    jupyter nbconvert --execute --to notebook --output $file $file
done
