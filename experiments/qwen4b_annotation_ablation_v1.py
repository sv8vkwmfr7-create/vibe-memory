"""Fixed v2 selector with recorded v2 applicability versus no annotation."""
from experiments.qwen4b_selection_ablation_v1 import main


if __name__ == '__main__':
    main(annotation_ablation=True)
