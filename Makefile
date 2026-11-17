.PHONY: test preflight clean

test:
	python3 -m unittest discover -s tests -v

preflight:
	bash scripts/preflight-check.sh --dry-run

clean:
	find . \( -name "__pycache__" -o -name ".pytest_cache" \) -type d -prune -exec rm -rf {} +
	rm -f 00_linked.auto.tfvars.json
