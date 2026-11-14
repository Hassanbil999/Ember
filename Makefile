# Same targets as run.py (use `python run.py <target>` where make is unavailable).
PY ?= python
.PHONY: start dev setup fetch ingest build test e2e
start:  ; $(PY) run.py start
dev:    ; $(PY) run.py dev
setup:  ; $(PY) run.py setup
fetch:  ; $(PY) run.py fetch
ingest: ; $(PY) run.py ingest
build:  ; $(PY) run.py build
test:   ; $(PY) run.py test
e2e:    ; $(PY) run.py e2e
