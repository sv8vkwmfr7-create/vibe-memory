"""Paired official positive/abstention diagnostic with unchanged local settings."""
from experiments.qwen4b_external_abstention_v1 import main


if __name__ == '__main__':
    main(include_positive_pairs=True)
