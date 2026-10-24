"""Date-example-only prompt revision; reuse the frozen v1 runtime."""
from experiments.qwen4b_staged_selection_v1 import ASSESS_PROMPT, main


ASSESS_PROMPT_V2 = ASSESS_PROMPT.replace(
    '"target_date":"YYYY-MM-DD或null"', '"target_date":"2026-10-01"'
).replace(
    'target_date必须为真实YYYY-MM-DD日期字符串或JSON null。',
    '上面的日期仅为格式示例，请按本题时间填写，不能照抄。'
    '日期字段示例：已知日期时为"target_date":"2026-09-12"；'
    '无法确定日期时为"target_date":null。'
    'null不能加引号，不能输出字符串"null"。'
    'target_date必须为真实YYYY-MM-DD日期字符串或JSON null。'
)


if __name__ == '__main__':
    main(assess_prompt=ASSESS_PROMPT_V2)
