.PHONY: help test preflight audit-suite clean

help:
	@echo "Targets: make preflight | make test | make audit-suite | make clean"

test:
	python3 -m unittest discover -s tests -v

preflight:
	bash scripts/preflight-check.sh --dry-run

audit-suite:
	python3 scripts/audit-suite-uniformity.py

clean:
	find . \( -name "__pycache__" -o -name ".pytest_cache" \) -type d -prune -exec rm -rf {} +
	rm -f 00_linked.auto.tfvars.json
