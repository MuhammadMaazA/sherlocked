ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PY := $(ROOT).venv/bin/python
export PATH := $(HOME)/.local/node/bin:$(PATH)

.PHONY: test api web build

test:
	cd $(ROOT)backend && $(PY) -m pytest -q

api:
	cd $(ROOT) && VIDEO_PROVIDER=$${VIDEO_PROVIDER:-vast} $(PY) -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

web:
	cd $(ROOT)frontend && npm run dev

build:
	cd $(ROOT)frontend && npm run build
