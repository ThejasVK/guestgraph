.PHONY: install test demo api lambda clean
install:
	pip install -e ".[dev]"
test:
	ruff check src tests aws && pytest -q
demo:
	guestgraph demo
api:
	uvicorn guestgraph.api:app --reload
lambda:
	rm -rf aws/build && pip install . -t aws/build && cp aws/lambda_handler.py aws/build/
clean:
	rm -rf data out aws/build .pytest_cache **/__pycache__ *.egg-info src/*.egg-info
