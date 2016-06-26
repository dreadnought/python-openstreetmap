#!/bin/bash
#
# Author: Patrick Salecker <mail@salecker.org>

for i in $(seq 1 3 15); do
	date
	list=$i,$(($i+1)),$(($i+2))
	echo $list
	python tilegen_multi.py $list
done
