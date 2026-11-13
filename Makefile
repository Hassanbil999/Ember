# Same targets as run.py (use `python run.py <target>` where make is unavailable).
PY ?= python
.PHONY: setup fetch fixture ingest train dev api web test all demo-off demo-on
setup:    ; $(PY) run.py setup
fetch:    ; $(PY) run.py fetch
fixture:  ; $(PY) run.py fixture
ingest:   ; $(PY) run.py ingest
train:    ; $(PY) run.py train
dev:      ; $(PY) run.py dev
api:      ; $(PY) run.py api
web:      ; $(PY) run.py web
test:     ; $(PY) run.py test
all:      ; $(PY) run.py all
demo-off: ; $(PY) run.py demo off
demo-on:  ; $(PY) run.py demo on
