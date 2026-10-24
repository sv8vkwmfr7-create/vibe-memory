"""Scope ambiguity and insufficient-evidence prompt experiment, not production."""
from experiments.qwen4b_staged_selection_v1 import SELECT_PREFIX, main
from experiments.qwen4b_staged_selection_v2 import ASSESS_PROMPT_V2


SCOPE_EVIDENCE_RULES = '''优先核对以下规则：范围只能来自question和本题scope，不能把候选的范围当成用户已经指定的范围。若用户没有指定环境，而关于所问属性的候选分别描述不同环境，必须标记ambiguous，各环境相关候选标记uncertain，不能默认生产环境，不能按候选顺序猜测。若用户明确指定环境、租户或操作，则其他范围的记录为inapplicable，不因同一服务名称就匹配。审计、操作人、格式、备份等记录若不提供所问属性的值或其未知状态，不能作为答案证据；明确说明该属性已更新但新值未记录的匹配范围记录，是说明无法确认的uncertain证据。'''
ASSESS_PROMPT_V3 = SCOPE_EVIDENCE_RULES + '\n' + ASSESS_PROMPT_V2
SELECT_PREFIX_V3 = SCOPE_EVIDENCE_RULES + '''选择时重新对照原题和候选原文，不盲从applicability。范围不明确时保留不同范围关于所问属性的两条记忆供澄清，不只选生产环境。若匹配范围记录仅说明所问属性已更新但内容未知，可选该记录说明无法确认；不能用别的环境或不提供所问属性的审计记录补足答案。没有能支持所问属性或其未知状态的证据时，selected_ids为空数组。''' + SELECT_PREFIX


if __name__ == '__main__':
    main(assess_prompt=ASSESS_PROMPT_V3, select_prefix=SELECT_PREFIX_V3)
