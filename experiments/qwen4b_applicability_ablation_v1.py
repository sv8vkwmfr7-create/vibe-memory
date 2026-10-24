"""Compare recorded v2/v3 applicability with the same v2 selection prompt."""
from experiments.qwen4b_selection_ablation_v1 import main


if __name__ == '__main__':
    main(applicability_ablation=True)
