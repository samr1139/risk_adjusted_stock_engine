.PHONY: install pipeline prices metrics scores serve clean

install:
	pip install -r requirements.txt

prices:
	python -m src.pull_prices

metrics:
	python -m src.compute_metrics

scores:
	python -m src.score_stocks

pipeline: prices metrics scores
	@echo "Pipeline complete."

serve:
	python -m src.api

clean:
	rm -f data/market.db
	@echo "Database removed. Re-run 'make pipeline' to rebuild."
