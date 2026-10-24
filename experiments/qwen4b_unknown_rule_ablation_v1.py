"""Isolate matching-scope unknown-updated-value evidence on frozen inputs."""
from experiments.qwen4b_single_stage_v2 import main


UNKNOWN_RULE = '补充选择规则：匹配范围的记录明确说所问属性已更新但新值未知时，选取该未知记录；不选未说明所问属性的审计、格式或操作人记录。'


if __name__ == '__main__':
    main(rules=UNKNOWN_RULE)
