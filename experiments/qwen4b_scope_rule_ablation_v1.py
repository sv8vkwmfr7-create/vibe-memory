"""Isolate the missing-scope clarification rule on frozen single-stage inputs."""
from experiments.qwen4b_single_stage_v2 import main


SCOPE_RULE = '补充选择规则：题目未指定环境或租户，而候选给出不同范围的所问属性值时，选取两种范围的证据用于澄清，不默认生产环境。'


if __name__ == '__main__':
    main(rules=SCOPE_RULE)
