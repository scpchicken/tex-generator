.PHONY: build test

build:
	python3 texgen.py rando.c

test:
	python3 test.py