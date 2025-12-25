#        conda create -n mlfs python==3.11	
#        conda activate mlsfs
#	conda install twofish clang -y

include .env
export $(shell sed 's/=.*//' .env)
	
check-venv:
	@if [ -n "$$CONDA_DEFAULT_ENV" ]; then \
		echo "You are in a Conda environment: $$CONDA_DEFAULT_ENV"; \
	elif python -c 'import sys; exit(0 if hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix) else 1)'; then \
		echo "You are running in a Python virtual environment."; \
	else \
		echo "No virtual environment or Conda environment detected. Please create and activate one first, then re-'make install'"; \
		exit 1; \
	fi 

install: check-venv
	pip install -r requirements.txt

install-recommender: check-venv
	pip install -r requirements-llm.txt

gef-clean:
	python utils/clean_hopsworks_resources.py gef

gef-features:
	python scripts/1_feat_back_param.py

gef-train:
	python scripts/3_training_pipeline.py

gef-inference:
#	python scripts/2_feature_pipeline.py
	python scripts/4_inference_pipeline.py

gef-all: aq-features aq-train aq-inference

