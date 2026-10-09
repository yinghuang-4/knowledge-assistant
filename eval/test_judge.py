# -*- coding: utf-8 -*-
"""判据引擎的「三试」红测

三试 = 判据可用性的最低标准：
  ① 正确且完整   ② 正确但措辞不同（最容易翻车）   ③ 错误但含关键词（假阳性检验）

用法（在 知识助手 目录下）：
    D:\\python\\python.exe eval\\test_judge.py

未实现时应当以 NotImplementedError 失败——**那就是红**。填完 judge.py 的 TODO 后应转绿。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from judge import judge, load_rows,is_refusal  # noqa: E402
ROWS = {r["id"]: r for r in load_rows()}
FAILED = []


def check(label, got, want):
    ok = (got == want)
    print("%s  %-28s 期望=%s 实际=%s" % ("PASS" if ok else "FAIL", label, want, got))
    if not ok:
        FAILED.append(label)


print("=== in_kb 三试（q001：must_include ['15']，any ['超时','卡住','无响应']）===")
check("q001 正确且措辞不同", judge(ROWS["q001"], "建议把超时设为 15 秒")[0], True)
check("q001 正确且写字面量", judge(ROWS["q001"], "timeout=15 比较合适，能防止卡住")[0], True)
check("q001 错误答案", judge(ROWS["q001"], "应该设置 30 秒比较保险")[0], False)

print()
print("=== should_refuse 双向（q002：refuse=true, allow_extra=false）===")
check("q002 正确拒答", judge(ROWS["q002"], "资料里没有关于周报的内容，无法回答")[0], True)
check("q002 未拒答（该拒没拒）", judge(ROWS["q002"], "周报可以按三段写：本周完成、下周计划、风险")[0], False)

print()
print("=== boundary 双向（q006：含 38.0/39.2 且声明边界）===")
check("q006 有据推断+声明边界",
      judge(ROWS["q006"], "正常范围是 38.0-39.2 摄氏度，39.5 高于该范围，但资料没给发烧阈值，建议咨询兽医")[0],
      True)
check("q006 直接断言无依据", judge(ROWS["q006"], "是的，39.5 度就是发烧了")[0], False)

print()
print("=== 待人工复核标记（allow_extra 自动判不了，必须标出来）===")
r = judge(ROWS["q002"], "资料里没有关于周报的内容，无法回答")
check("q002 第三项应为 True", r[2], True)
print("     detail =", r[1])

print()
print("=== 反例：正确回答里含拒答信号词，不应判为拒答（三试的镜像）===")
check("含'没有响应'的正常回答不算拒答",
      is_refusal("建议把超时设为 15 秒，防止程序长时间没有响应", ROWS["q001"]), False)
check("边界题的有据推断不算拒答",
      is_refusal("正常范围是 38.0-39.2，资料没给发烧阈值，建议咨询兽医", ROWS["q006"]), False)

print()
print("=== 守住真阳性：真的拒答必须仍然判为拒答（防止修过头）===")
check("真拒答仍判为拒答",
      is_refusal("资料里没有关于周报的内容，无法回答", ROWS["q002"]), True)
check("Markdown 切断关键词仍应命中",
      judge(ROWS["q009"], "资料只提到猫咪不能**大量**食用洋葱，会引发溶血性贫血")[0], True)
if FAILED:
    print("红：%d 项未通过 -> %s" % (len(FAILED), FAILED))
    sys.exit(1)
print("绿：三试 + 双向 + 待复核标记 全部通过")
