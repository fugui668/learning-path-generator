# 🎯 个性化学习路径生成器 v4.0

根据个人学习目标、当前水平、可用时间，自动生成有序学习计划 + 资源推荐 + 进度检验方案。

## 快速开始

```bash
# 交互式生成路径（推荐）
python3 learning_path.py        # 兼容旧方式（shim）
python3 -m learning_path        # 新方式（推荐）

# 查看示例（5个领域）
python3 -m learning_path --demo

# 进度追踪 + 动态调整建议
python3 -m learning_path --track

# 记录今日学习日志
python3 -m learning_path --log

# 查看历史日志
python3 -m learning_path --show-log

# 打印 ASCII 进度图表（带 ANSI 颜色）
python3 -m learning_path --chart

# 导出 PDF 报告
python3 -m learning_path --export

# 查看所有可用领域
python3 -m learning_path --list-domains

# 新增自定义领域（交互式）
python3 -m learning_path --add-domain

# 查看版本号
python3 -m learning_path --version
```

**无需安装任何依赖，仅需 Python 3.6+**（PDF 导出可选安装 `pip install reportlab`）

---

## 支持领域（9个）

| 领域 | 触发关键词 |
|------|-----------|
| 编程 | Python、Java、代码、开发、算法等 |
| 数据分析 | 数据、机器学习、AI、统计等 |
| 英语 | 英语、雅思、托福、IELTS等 |
| 中文 | 中文、汉语、HSK、Chinese等 |
| 西班牙语 | 西班牙语、Spanish、DELE等 |
| 设计 | 设计、UI、UX、Figma、视觉等 |
| 产品 | 产品、PRD、需求、原型等 |
| 写作 | 写作、文章、创作、博客等 |
| 通用 | 其他任意目标 |

---

## 功能说明

### 1. 信息收集
交互式输入 4 项：学习目标 / 当前水平（零基础~高级）/ 每周时间 / 期望周期

### 2. 学习路径生成
- 自动识别领域，匹配对应模板
- 按当前水平决定起始阶段（入门/进阶/高级）
- **周数不足时智能收缩**：总周数 < MIN_STAGE_WEEKS 时不强行展开下一阶段
- 按模板权重预分配各阶段周数，防止某阶段吃完所有时间

### 3. 资源推荐
每阶段差异化推荐 4 类资源（入门/进阶/高级各不同）

### 4. 掌握度检验
每阶段 3 个检查点：概念自测 / 实操验证 / 成果展示

### 5. 进度追踪（--track）
**自动根据路径生成日期推算当前第几周**，确认或手动修改后精确定位所在步骤；再输入落后周数，按 3 档给出动态调整建议

### 6. 学习日志（--log / --show-log）
**自动匹配当前周对应步骤**，一键确认；也可手动选择其他步骤。记录学习时长、里程碑完成情况、备注，持久化到 `learning_log.json`

### 7. ASCII 进度图表（--chart）
- 总进度条 + 各阶段进度条
- 最近 7 天每日学习柱状图
- 里程碑完成统计

### 8. PDF 导出（--export）
生成 `learning_path_report.pdf`，包含完整路径信息。未安装 reportlab 时自动降级为 txt。

---

## 5 个示例路径

运行 `python3 -m learning_path --demo` 查看：

| # | 目标 | 水平 | 每周时间 | 周期 |
|---|------|------|---------|------|
| 1 | 零基础学 Python 编程，目标做数据分析 | 零基础 | 10h | 16 周 |
| 2 | 提升英语口语，备考雅思 7 分 | 初级 | 8h | 20 周 |
| 3 | 深入学习机器学习，达到可参加 Kaggle 竞赛水平 | 中级 | 15h | 12 周 |
| 4 | 零基础学西班牙语，目标 DELE B1 | 零基础 | 6h | 24 周 |
| 5 | 学中文，备考 HSK 5 级 | 初级 | 8h | 20 周 |

---

## 路径生成逻辑说明

### 整体流程

```
用户输入（目标 / 水平 / 时间 / 周数）
        ↓
  领域检测（detect_domain）
        ↓
  阶段选择（_select_and_allocate）
        ↓
  步骤构建（_build_steps）
        ↓
  输出 / 保存 / 导出
```

---

### 第一步：领域检测

**函数：** `detect_domain(goal)`

用关键词命中数对所有领域打分，取分最高者作为识别结果。

```
"我想学 Python 做数据分析"
  → 编程命中：python (1)
  → 数据分析命中：数据分析 (1) + python分析 (1) = 2
  → 数据分析胜出 ✅
```

**平局处理：** 命中数相同时，用领域的 `priority` 字段决胜（数字越大越优先）。

**否定词过滤：** 「不想/不学/不做/不打算/不考虑」后紧跟的关键词不参与计分，防止「不想学 Python，要学设计」误识别为编程。过滤范围不跨标点，避免误遮后续句子。

**兜底：** 无任何领域命中时，返回「通用」，走通用模板。

---

### 第二步：阶段选择与周数分配

**函数：** `_select_and_allocate(start_stage, total_weeks, domain)`

每个领域固定三个阶段：**入门 → 进阶 → 高级**，各阶段有预设权重比例（如 4:3:3）。

**起始阶段规则：**

| 用户水平 | 起始阶段 |
|---------|---------|
| 零基础 / 初级 | 入门 |
| 中级 | 进阶 |
| 高级 | 高级 |

**周数不足时智能收缩：**

- 每阶段最少 `MIN_STAGE_WEEKS`（= 3）周，低于此值不展开该阶段
- 剩余周数优先保证当前阶段，不够开下一阶段时直接停止
- 极端情况（total_weeks = 1）：只展开一个阶段，所有周数全给它

**周数精确保证：** 分配算法确保所有阶段周数之和 **严格等于** `total_weeks`，不会多不会少。

---

### 第三步：步骤构建

**函数：** `_build_steps(stage_name, alloc_weeks, hours_per_week, template_steps, week_cursor)`

每个阶段有若干模板步骤，每步有预设参考周数。按比例缩放到实际分配周数：

```
模板步骤权重：[1, 2, 1]  → 总权重 4
实际分配：12 周
→ 各步骤：3周、6周、3周
```

**步骤合并（极端情况）：** 若实际分配周数少于步骤数（如 2 周但有 4 个步骤），从末尾开始两两合并，直到步骤数 ≤ 分配周数。合并时名称用 `&` 连接，里程碑拼接两段摘要（各取前 20 字），保留关键信息。

**week_range 计算：** 步骤的起止周基于全局 `week_cursor` 累加，确保跨阶段连续不重叠（如第 1~3 周、第 4~7 周、第 8~12 周……）。

---

### 关键取舍

| 取舍项 | 选择 | 原因 |
|--------|------|------|
| 实现方式 | CLI（非 Web/App） | 零依赖，快速可运行，专注核心逻辑 |
| 资源推荐 | 类型推荐（非真实链接） | 避免链接失效，普适性强 |
| 领域覆盖 | 9 大领域 + 自定义扩展 | domains.json 可随时新增，无需改代码 |
| 路径算法 | 规则引擎（非 AI API） | 本地运行，输出稳定可预期，无网络依赖 |
| 领域识别 | 关键词计数 + 否定词过滤 + priority 决胜 | 准确率高，边界处理完善 |
| 周数不足时 | 智能收缩阶段数 | 避免每阶段时间极短、学习深度不足 |
| 步骤合并 | 里程碑拼接两段摘要 | 极端周数时合并不丢关键信息 |
| 进度定位 | 按当前周精确匹配步骤 | 用户清晰知道自己在哪一步 |

### 未完成项
- [ ] 接入 AI API 动态生成路径（OpenAI / 本地大模型）

---

## 文件结构

```
learning-path-generator/
├── learning_path.py              # 向后兼容 shim（调用包入口）
├── learning_path/                # 主包（v4.0 模块化）
│   ├── __init__.py               # 导出公共 API
│   ├── __main__.py               # python -m learning_path 入口
│   ├── _version.py               # 版本号
│   ├── domains.py                # 领域注册表加载
│   ├── core.py                   # 核心路径生成逻辑
│   ├── log.py                    # 日志读写
│   ├── render.py                 # 输出渲染（CLI/PDF）
│   ├── cli.py                    # 命令行交互入口
│   └── domains.json              # 领域配置数据
├── test_learning_path.py         # 单元测试（91个）
├── README.md                     # 本文件
├── my_path.json                  # 生成后保存的路径（gitignore）
├── learning_log.json             # 学习日志（gitignore）
└── learning_path_report.pdf      # 导出的 PDF（gitignore）
```

### 新增自定义领域

**方式一：交互式添加（推荐）**
```bash
python3 -m learning_path --add-domain
```
按提示输入领域名、关键词、三阶段步骤即可，自动写入 `domains.json`。

**方式二：直接编辑 learning_path/domains.json**
在 `domain_registry` 对象下新增一个键，格式参照现有领域结构：
```json
"日语": {
  "priority": 7,
  "keywords": ["日语", "japanese", "jlpt", "n1", "n2"],
  "stages": {
    "入门": [{"name": "五十音图", "weeks": 2, "milestone": "默写全部假名"}],
    "进阶": [{"name": "N4/N3 词汇语法", "weeks": 4, "milestone": "通过 N3 模拟题"}],
    "高级": [{"name": "N2/N1 冲刺", "weeks": 4, "milestone": "N1 模拟 120 分以上"}]
  }
}
```

## 测试

```bash
python3 -m unittest test_learning_path -v
```

覆盖（91 个测试）：
- 输入解析（parse_float / parse_int）
- 领域检测（含否定词过滤 / priority 决胜）
- 路径生成边界（极短 / 极长 / 各等级）
- 步骤连续性 / hours_total 正确性
- 进度定位 / 当前周推算 / 步骤匹配
- 日志读写 / 空文件 / 损坏文件
- **边界输入**（total_weeks=1/100，hours=1/100，空目标，等级两端）
- **异常输入**（parse_int("")、detect_domain(None)、不存在路径）
- **CLI mock 测试**（track_mode / add_log_entry / interactive_mode 完整流程）
- 100 组随机参数压测

## 🌐 Web 界面

```bash
pip install flask
python3 -m learning_path --web
# 访问 http://localhost:5000
```

支持功能：生成学习路径 / 进度追踪打卡 / 图表可视化 / PDF 导出

也可以直接在 `web/` 目录下启动：

```bash
cd web
python3 app.py
```
