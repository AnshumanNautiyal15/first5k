TAILWIND_VERSION ?= v3.4.17
TAILWIND := bin/tailwindcss
PY := .venv/bin/python

UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)
ifeq ($(UNAME_S),Darwin)
  TW_OS := macos
else
  TW_OS := linux
endif
ifeq ($(filter $(UNAME_M),arm64 aarch64),)
  TW_ARCH := x64
else
  TW_ARCH := arm64
endif

.PHONY: install tailwind-install css css-watch run test migrate

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt

$(TAILWIND):
	mkdir -p bin
	curl -sSL -o $(TAILWIND) https://github.com/tailwindlabs/tailwindcss/releases/download/$(TAILWIND_VERSION)/tailwindcss-$(TW_OS)-$(TW_ARCH)
	chmod +x $(TAILWIND)

tailwind-install: $(TAILWIND)

css: $(TAILWIND)
	$(TAILWIND) -c tailwind.config.js -i static/src/input.css -o static/css/app.css --minify

css-watch: $(TAILWIND)
	$(TAILWIND) -c tailwind.config.js -i static/src/input.css -o static/css/app.css --watch

migrate:
	$(PY) manage.py migrate

run:
	$(PY) manage.py runserver

test:
	.venv/bin/pytest
