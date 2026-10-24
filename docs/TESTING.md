# 测试说明 | Testing Guide

本文档说明本项目如何测试、覆盖哪些场景、如何复现结果，以及哪些内容**尚未**被自动化测试覆盖。

## 1. 运行测试

环境要求：Python 3.12，已安装 `requirements.txt` 中的依赖。

```powershell
# 项目根目录
python -m pytest -q
```

带详细输出：

```powershell
python -m pytest -v
```

只跑某个模块：

```powershell
python -m pytest tests/test_market_state.py -v
```

`pytest.ini` 已配置测试发现规则，无需额外参数。

## 2. 最近一次完整测试结果

```text
101 passed, 21 subtests passed in 2.02s
```

执行环境：本地 Windows + Python 3.12 + `.venv`。

该结果代表**本地自动化测试**通过，不代表所有实时 API 状态、部署环境或历史行情已验证。

## 3. 测试覆盖范围

按题目要求的三类组织。

### 3.1 主链路

覆盖「快照获取 → 数据质量 → 市场广度 → 状态分类 → 研究报告 → AI 解读」全链路的关键节点。

| 测试文件 | 覆盖内容 |
|---|---|
| `test_market_data.py` | 股票/指数快照请求、分页拼接、字段解析、返回结构 |
| `test_market_analysis.py` | 上涨/下跌/平盘分类、有效分母口径、缺失值不计入 |
| `test_market_state.py` | 规则阈值边界、指数方向组合、切换条件生成 |
| `test_research_report.py` | 事实/解释/假设分段、证据质量字段、`historically_validated=False` |
| `test_llm_analysis.py` | AI 解读输入组装、输出结构、缓存键一致性 |
| `test_app_time_format.py` | 时间戳格式化（毫秒/秒、时区、无效值） |

### 3.2 数据缺失与接口失败

| 测试文件 | 覆盖内容 |
|---|---|
| `test_data_quality.py` | 记录数不符、重复代码、无效涨跌幅、缺失比例超阈值 |
| `test_index_quality.py` | 指数接口缺失/为空时质量判定降级 |
| `test_time_gap.py` | 股票与指数接口时间差计算、阈值判定 |
| `test_market_freshness.py` | 时间戳过期、缺失、未来时间、双源综合判定 |

关键断言：**门槛未通过时，不得静默生成"正常"结论**——即 `descriptive_statistics_ready=False` 时不应展示市场广度，`research_ready=False` 时报告应带限制标记。

### 3.3 极端与合规边界

| 测试文件 | 覆盖内容 |
|---|---|
| `test_market_session.py` | 周末、盘前、午休、盘后、无效时间戳的时段判定 |
| `test_research_applicability.py` | 交易日历未验证、时段未确认、新鲜度未通过时的适用性降级 |
| `test_llm_analysis.py` | AI 输出不得包含涨跌预测/仓位建议的结构约束；模型调用失败的异常路径 |

合规边界的关键设计：`assess_market_state()` 返回的 `method` 中硬编码 `historically_validated: False`，测试会校验该字段存在且为 `False`，防止前端误标"已验证"。

## 4. 未覆盖内容（明确声明）

以下内容**没有**自动化测试覆盖，不应声称已验证：

- **官方交易日历**：项目未接入交易所权威日历，周末/时段判断是简化规则。
- **全市场历史回测**：抽样股票日线不构成全市场历史快照，不能验证阈值。
- **市值加权广度**：当前广度按有效记录数统计，非市值加权。
- **真实 API 稳定性**：测试使用构造数据或 mock，不覆盖上游服务超时、限流、字段变更。
- **部署环境**：Streamlit Cloud 的 Secrets、网络、休眠唤醒行为未纳入自动化测试，需手动验证。
- **AI 输出质量**：测试校验结构与合规约束，不评估模型生成内容的语义正确性。

## 5. 手动验证清单

部署后每次发布应人工过一遍：

- [ ] 页面加载，标题不被顶栏遮挡
- [ ] 获取快照成功，指数卡片与徽章正常
- [ ] 数据诊断 Tab 五个面板可展开
- [ ] 数据质量门槛未通过时，市场广度不展示
- [ ] AI 解读按钮生成结果，显示模型名与时间
- [ ] 更换快照后 AI 缓存正确失效

## 6. 复现与更新

- 修改 `src/` 下任意模块后，必须重跑 `python -m pytest -q` 并更新本文档第 2 节。
- 新增测试文件后，在 3.1–3.3 对应表格中补充一行。
- 若测试失败，先判断是代码缺陷还是断言过时，不得直接删除断言。

## 7. 与 AI 使用记录的关系

AI 参与测试设计、断言补全和失败排查。测试结果由开发者在本地实际执行确认。

详见 [`AI_USAGE_AND_VALIDATION.md`](AI_USAGE_AND_VALIDATION.md)。