## ADDED Requirements

### Requirement: 合作方列表统计列

系统 SHALL 在合作方列表表格展示情报与源数据统计，并支持点击钻取。

#### Scenario: 情报列格式

- **WHEN** 渲染合作方列表
- **THEN** MUST 展示 `intel_medium_plus/intel_total` 格式（如 `5/12`）
- **且** 点击 MUST 打开合作方详情情报子 Tab

#### Scenario: 源数据列

- **WHEN** 渲染合作方列表
- **THEN** MUST 展示 `raw_total`（无 default_task 时显示 `-` 或 `0`）
- **且** 点击 MUST 打开合作方详情源数据子 Tab

### Requirement: 任务 ignore_before 表单

系统 SHALL 在监测任务创建/编辑 Modal 提供「忽略早于」日期字段，映射 `business_spec.ignore_before`。

#### Scenario: 保存与展示

- **WHEN** 管理员保存任务且填写日期
- **THEN** MUST 持久化到 business_spec
- **WHEN** 再次打开编辑
- **THEN** MUST 回显已保存日期

### Requirement: 管理员数据清理 UI

系统 SHALL 为管理员提供批量清理 Modal，支持清理 raw 或 intel。

#### Scenario: 任务 Tab 入口

- **WHEN** 管理员在监测任务 Tab 打开清理
- **THEN** MUST 预填 `task_id`
- **且** MUST 支持 dry_run 预览与确认删除

#### Scenario: 合作方详情入口

- **WHEN** 管理员在合作方详情打开清理
- **THEN** MUST 预填 `partner_id`
- **且** MUST 提供关联任务选择（默认 default_task）

#### Scenario: 非管理员不可见

- **WHEN** 用户非管理员且 `admin.enabled=true`
- **THEN** 清理入口 MUST 隐藏或禁用
