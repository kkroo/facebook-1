client server:
	make clean
	ln -s setup_$@.py setup.py
	make build
	rm setup.py
build:
	python setup.py --command-packages=stdeb.command bdist_deb
clean:
	rm -rf deb_dist build *.egg-info setup.py
