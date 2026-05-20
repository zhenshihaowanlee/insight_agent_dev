请作为本仓库的 reviewer 检查预算控制和质量闸门。

阅读：
- AGENTS.md
- docs/04_BUDGET_AND_MODEL_ROUTING.md
- src/zyw_insight/budget.py
- src/zyw_insight/quality_gates.py
- tests/

请回答：
1. 当前代码是否足以阻止无证据强结论？
2. 是否覆盖 average-only、baseline fairness、工艺约束缺失、jitter/bandwidth 术语混淆？
3. 是否符合 PoC 30–80 USD/月、正式版 150–250 USD/月、软上限 300 USD/月的控制逻辑？
4. 给出最小修复方案并实现。
5. 运行 make test。
