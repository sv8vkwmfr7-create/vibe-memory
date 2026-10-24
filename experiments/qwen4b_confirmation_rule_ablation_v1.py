"""Isolate confirmed/unverified evidence selection on frozen single-stage inputs."""
from experiments.qwen4b_single_stage_v2 import main


CONFIRMATION_RULE = '补充选择规则：题目询问某说法是否已确认时，已确认旧值和未核实新说法都是解释无法确认所需的证据，可同时选取，不能把未核实说法当成事实。'


if __name__ == '__main__':
    main(rules=CONFIRMATION_RULE)
