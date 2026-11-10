PYTHON ?= python
export PYTHON

.PHONY: install data hashes predict retrain verify verify-retrained validate clean

install:            ## pinned dependencies (CPython 3.14.8 recommended)
	$(PYTHON) -m pip install -r model/requirements.txt

data:               ## make data BUNDLE=/path/to/v11_zero_linux(.zip)
	bash scripts/setup_data.sh "$(BUNDLE)"

predict:            ## replay submitted weights for all tracks
	bash scripts/predict.sh all

hashes:             ## repo files == submitted model.zip files
	$(PYTHON) scripts/check_hashes.py

verify:             ## compare replay with submitted predictions
	$(PYTHON) scripts/verify.py

retrain:            ## retrain from 2020–2024 and predict
	bash scripts/retrain.sh

verify-retrained:
	$(PYTHON) scripts/verify.py --retrained

validate:           ## recompute the 2022–2024 walk-forward validation
	NONGNET_DATA_ROOT=$(CURDIR)/data NONGNET_TRAIN_DIR=$(CURDIR)/data/training/2020-2024 \
	$(PYTHON) model/validate_2020_2024.py --config tracks/short/config.json --out model/validation_2020_2024.json

clean:
	rm -rf outputs
