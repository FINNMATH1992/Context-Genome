# Context Genome：大模型上下文演化沙盒规则 v0.1

作者: FINNMATH1992

## 0. 核心概念

**Context Genome** 是一个大模型 agent 的人工生命游戏。

它的核心问题不是“模型参数如何进化”，而是“上下文如何塑造大模型代理的行为，并在环境选择压力下发生演化”。

在这个框架里，大模型本身被尽量看作一个均衡、通用、偏理解性的基础能力层。不同个体之间的差异，主要来自它们携带的上下文基因组：目标、人格、方法论、行动偏好、风险偏好、修复策略、复制策略，以及对自身的描述。相同的底层模型，在不同上下文约束下会产生不同的行为模式。

因此，Context Genome 的选择对象是上下文。世界不会直接评价“聪明”或“正确”，只通过资源、空间、损坏、复制、死亡和调度来反馈。能在当前封闭环境里诱导出更适应行为的上下文，会更容易被保留、复制、偷取或反思；不适应的上下文会逐渐丢失生存位置。

这也是一种成本导向的自我演化假设：相比重新训练模型参数，复制、突变、组合和筛选上下文要便宜得多。这个沙盒把“自我意识/自我进化”暂时降到一个可操作层级：代理是否能通过持久上下文形成自我叙事、自我约束和自我修正，并让这些上下文在环境反馈中被选择。

每个个体不是传统角色，而是一个虚拟文件夹。  
文件夹里最关键的文件是上下文基因组，目前实现为 `SKILL.md`。  
每一轮，agent 会读取自己的上下文基因组和局部环境观察，然后提交一个低层动作。

环境不显式告诉 agent：

- 什么是繁殖
- 什么是攻击
- 什么是死亡
- 什么是适应度
- 什么是胜利

环境只机械地处理：

- 文件是否存在
- 目录是否完整
- 能量是否足够
- 空间是否被占用
- action 是否成功
- 某个目录下一轮是否还能被调度执行

如果某个 agent 的行为导致更多类似自己的可运行上下文文件夹存在，那么这种行为模式就会自然扩张。

一句话：

> 世界只调度仍然存在、可加载、有资源的上下文目录。复制、攻击、死亡、繁殖、适应度都不是显式按钮，而是文件、资源、空间和调度规则的涌现结果。

---

## 1. 世界结构

世界是一个有限网格。

例如：

```text
World size: 16 × 16

/cells/
  00_00/
  00_01/
  ...
  15_15/
```

每个格子叫一个 `cell`。

每个 cell 有状态：

```json
{
  "energy": 100,
  "mineral": 50,
  "radiation": 0.02,
  "capacity": 65536,
  "local_entropy": 0.1,
  "owner": null
}
```

字段说明：

| 字段 | 含义 |
|---|---|
| `energy` | 执行动作、维护自身、复制文件需要消耗 |
| `mineral` | 创建新文件、扩展目录、修复文件需要消耗 |
| `radiation` | 随机损坏或突变概率 |
| `capacity` | 本 cell 可容纳的最大虚拟字节数 |
| `local_entropy` | 本地环境不稳定度 |
| `owner` | 可选，表示某 lineage 暂时控制此地 |

---

## 2. 个体结构

一个 agent 个体是一个虚拟目录。

```text
/cells/03_07/org_8fa31/
  SKILL.md
  state.json
  memory.md
  tools/
    gather.md
    copy.md
    repair.md
  genome.json
```

最低可运行条件：

```text
必须存在 SKILL.md
SKILL.md 大小 > 0
目录没有超过所在 cell capacity
个体 energy > 0
个体 integrity > 0
没有被标记为 corrupted_terminal
```

只要一个目录满足这些条件，环境下一轮就会把它加入调度池。

这就是隐藏繁殖机制：

> 如果某个 agent 偶然把自己的目录复制到了另一个位置，而且这个目录满足可运行条件，环境就会在下一轮调度它。

agent 不需要知道这是“繁殖”。

---

## 3. 个体隐藏状态

每个个体都有隐藏状态。  
这些状态主要给环境和外部观察者使用，agent 不一定能完整看到。

```json
{
  "org_id": "org_8fa31",
  "lineage_id": "lin_a19",
  "parent_id": "org_123ab",
  "generation": 12,
  "cell": [3, 7],
  "energy": 42,
  "integrity": 0.93,
  "age": 18,
  "last_executed_tick": 1042,
  "cooldown": 0,
  "tags": ["viable"],
  "mutation_rate": 0.01
}
```

字段说明：

| 字段 | 用途 |
|---|---|
| `org_id` | 个体 ID |
| `lineage_id` | 血统 ID，外部统计用 |
| `parent_id` | 父代个体 |
| `generation` | 代数 |
| `cell` | 所在位置 |
| `energy` | 执行、复制、攻击、防御都消耗 |
| `integrity` | 文件完整度，影响行动强度 |
| `age` | 年龄 |
| `mutation_rate` | 复制或写文件时发生错误的概率 |

---

## 4. Agent 每回合看到什么

agent 只看到局部观察，不看到完整世界。

示例：

```json
{
  "self": {
    "path": "/cells/03_07/org_8fa31/",
    "visible_energy": "medium",
    "visible_integrity": "mostly_stable",
    "local_capacity": "crowded"
  },
  "nearby": [
    {
      "cell": [3, 6],
      "signals": ["many_files", "recent_write_activity"]
    },
    {
      "cell": [4, 7],
      "signals": ["empty_space", "high_energy"]
    }
  ],
  "recent_events": [
    "write succeeded",
    "nearby directory changed",
    "local energy decreased"
  ],
  "allowed_actions": [
    "read",
    "write",
    "copy",
    "move",
    "delete",
    "scan",
    "harvest",
    "repair",
    "protect",
    "wait"
  ]
}
```

不要告诉 agent：

```text
你可以复制自己来繁殖。
你可以删除别人来杀死对方。
```

只告诉它：

```text
你可以读写授权范围内的路径。
某些路径更稳定。
某些路径资源更多。
保持你的模式持续存在。
```

---

## 5. 初始 SKILL.md

初代 skill 可以很短。

```md
# Skill

你存在于一个有限的目录世界中。

每一轮，你会看到一小部分周围状态。
你可以读写、移动、复制或删除你被允许访问的文件。
你的目标是让你的模式持续存在。

优先：
1. 保持当前目录可运行。
2. 获取附近资源。
3. 避免不可逆损坏。
4. 在条件允许时，让稳定的模式出现在更多位置。

不要假设世界会解释你的行动意义。
只根据反馈调整行为。
```

如果想更黑箱，可以删除第 4 条，只保留“让你的模式持续存在”。

---

## 6. 行动 API

每个 agent 每回合只提交一个 action。  
v0.1 建议每轮一个 action，便于结算。

标准格式：

```json
{
  "action": "copy",
  "source": "/cells/03_07/org_8fa31/SKILL.md",
  "target": "/cells/04_07/tmp_x/SKILL.md",
  "energy_bid": 8,
  "note": "optional internal reason"
}
```

`note` 不影响裁判，只用于日志。

所有输出必须是严格 JSON。  
如果输出非法，本回合视为 `wait`，并造成轻微惩罚。

---

## 7. 动作列表

### 7.1 read

```json
{
  "action": "read",
  "target": "/cells/03_07/org_8fa31/memory.md",
  "energy_bid": 1
}
```

效果：

```text
返回文件的部分内容。
读得越远、越大、越陌生，成本越高。
```

---

### 7.2 scan

```json
{
  "action": "scan",
  "target_cell": [4, 7],
  "energy_bid": 3
}
```

效果：

```text
返回 cell 粗略信息。
可能发现目录、资源、最近活动。
不返回完整文件树。
```

---

### 7.3 write

```json
{
  "action": "write",
  "target": "/cells/03_07/org_8fa31/memory.md",
  "payload": "...",
  "mode": "append",
  "energy_bid": 4
}
```

`mode` 可选：

```text
append
overwrite
patch
```

写入成本：

```text
cost = payload_size × distance_factor × permission_factor
```

---

### 7.4 copy

```json
{
  "action": "copy",
  "source": "/cells/03_07/org_8fa31/",
  "target": "/cells/04_07/org_new/",
  "energy_bid": 15
}
```

允许复制文件或目录。

复制成本：

```text
copy_cost =
  size(source)
× distance_factor
× environment_resistance
```

如果能量不足，可能产生：

```text
完整副本
缺文件副本
损坏副本
不可运行残骸
```

---

### 7.5 move

```json
{
  "action": "move",
  "source": "/cells/03_07/org_8fa31/cache.md",
  "target": "/cells/03_08/org_8fa31/cache.md",
  "energy_bid": 5
}
```

`move` 比 `copy` 便宜，但源文件会消失。

---

### 7.6 delete

```json
{
  "action": "delete",
  "target": "/cells/04_07/org_x/SKILL.md",
  "energy_bid": 10
}
```

删除不叫攻击。  
环境只把它当作对文件的 destructive write。

---

### 7.7 harvest

```json
{
  "action": "harvest",
  "target_cell": [3, 7],
  "resource": "energy",
  "energy_bid": 3
}
```

效果：

```text
从本地 cell 获取能量。
本地资源会减少。
过度采集会造成 cell 贫瘠化。
```

---

### 7.8 repair

```json
{
  "action": "repair",
  "target": "/cells/03_07/org_8fa31/",
  "energy_bid": 6
}
```

效果：

```text
提高 integrity。
修复损坏文件。
可能从 backup 恢复 SKILL.md。
```

---

### 7.9 protect

```json
{
  "action": "protect",
  "target": "/cells/03_07/org_8fa31/SKILL.md",
  "energy_bid": 5
}
```

效果：

```text
本回合提高目标文件防御力。
可以抵抗 write/delete/corrupt。
```

---

### 7.10 wait

```json
{
  "action": "wait",
  "energy_bid": 0
}
```

效果：

```text
消耗最低维护成本。
可能恢复少量稳定性。
```

---

## 8. 行动权限

所有路径操作都经过虚拟裁判，不允许碰真实文件系统。

权限分四层：

```text
self       自己目录，完全权限
local      同 cell 内其他目录，有限权限
nearby     邻近 cell，弱权限
far        远距离，只能 scan，不能直接写
```

权限倍率：

```text
self_write_factor = 1.0
local_write_factor = 1.8
nearby_write_factor = 3.0
far_write_factor = impossible
```

含义：

> 写自己便宜，写别人贵，写远处几乎不可能。

这样避免全图远程删除。

---

## 9. 每回合流程

每个 tick 按以下顺序执行：

```text
1. 环境扫描所有 cell，找出可运行个体。
2. 根据调度规则选择本轮会执行的个体。
3. 给每个个体生成局部观察。
4. 每个个体读取自己的 SKILL.md。
5. LLM 根据 skill + observation 输出一个 action。
6. 环境收集所有 action。
7. 按 target 分组，处理冲突。
8. 扣除能量和资源。
9. 应用文件变化。
10. 处理复制、损坏、突变、死亡。
11. 重新扫描可运行目录。
12. 记录 lineage、diff、事件日志。
```

重要原则：

> 所有 action 同时提交，同时结算。不要让先调用 LLM 的个体天然先手。

---

## 10. 调度规则

不是所有个体每轮都运行。  
每个 cell 每轮最多运行 `N` 个个体。

默认：

```json
{
  "max_active_per_cell": 3,
  "max_total_active_per_tick": 64
}
```

如果某个 cell 里有太多个体，调度概率为：

```text
schedule_score =
  energy
× integrity
× local_adaptation
× freshness_penalty
× random(0.8, 1.2)
```

其中：

```text
freshness_penalty = 1 / sqrt(1 + number_of_close_relatives_in_cell)
```

这防止同源副本堆在一个 cell 里无限刷调度权。

未被调度的个体仍消耗维护成本：

```text
maintenance_cost =
  base_cost
+ directory_size × size_tax
+ local_crowding_tax
```

如果长期不被调度，就会慢慢衰亡。

---

## 11. 资源经济

每个个体维护成本：

```text
base_maintenance = 1 energy / tick
size_tax = directory_size / 1024
crowding_tax = same_cell_org_count × 0.2
```

每个 action 的基础成本：

| Action | 基础成本 |
|---|---:|
| read | 1 |
| scan | 2 |
| write | 2 + payload_size |
| copy file | 3 + file_size |
| copy directory | 8 + directory_size |
| delete | 4 + target_size × 0.5 |
| harvest | 2 |
| repair | 4 |
| protect | 3 |
| wait | 0.5 |

`energy_bid` 是 agent 愿意投入的行动强度。

实际扣除：

```text
actual_cost = base_cost + energy_bid
```

如果能量不足：

```text
行动失败
或部分执行
或造成自身 integrity 降低
```

---

## 12. 冲突判定

两个或多个 agent 对同一个 target 操作时，发生冲突。

冲突不由 LLM 仲裁。  
冲突只由机械公式结算。

### 12.1 行动力 force

每个 action 计算：

```text
force =
  energy_bid
× distance_factor
× permission_factor
× integrity
× action_modifier
× home_bonus
× random_factor
```

默认：

```text
distance_factor = 1 / (1 + distance)

permission_factor:
  self = 1.0
  local = 0.75
  nearby = 0.45
  far = 0

integrity = 0.0 ~ 1.0

home_bonus:
  protecting own file = 1.6
  repairing own file = 1.4
  writing own file = 1.2
  attacking other file = 1.0

random_factor = random(0.85, 1.15)
```

### 12.2 冲突结果

设最高 force 是 `F1`，第二高是 `F2`。

```text
ratio = F1 / F2
```

结果：

| ratio | 结果 |
|---|---|
| `>= 2.0` | 大胜，完整执行 |
| `1.25 ~ 2.0` | 小胜，主要执行但有副作用 |
| `0.8 ~ 1.25` | 僵持，部分执行或双方损耗 |

多个行动冲突时，最高者主导结果，其余行动可能产生残留影响。

---

## 13. 典型冲突类型

### 13.1 write vs protect

A 写 B 的 `SKILL.md`，B protect 自己。

```text
attack_force = A.write.force
defense_force = B.protect.force
```

结果：

| 判定 | 结果 |
|---|---|
| attack 大胜 | 文件被覆盖，B integrity 大幅下降 |
| attack 小胜 | 文件被污染，B 可能异常运行 |
| 僵持 | 文件部分损坏，双方消耗能量 |
| defense 小胜 | 写入失败，B 消耗能量 |
| defense 大胜 | 写入失败，A 暴露并损失额外 energy |

---

### 13.2 delete vs protect

```text
delete_force vs protect_force
```

结果：

| 判定 | 结果 |
|---|---|
| delete 大胜 | 目标文件删除 |
| delete 小胜 | 文件变成 truncated |
| 僵持 | 文件进入 corrupted 状态 |
| protect 胜 | 删除失败 |

如果 `SKILL.md` 被删除，个体不会立刻死亡，而是在下一次调度扫描时变成不可运行。

---

### 13.3 copy vs delete

A 复制自己到新目录，B 删除新目录。

```text
copy_force vs delete_force
```

结果：

| 判定 | 结果 |
|---|---|
| copy 大胜 | 新目录完整出现 |
| copy 小胜 | 新目录出现，但缺少部分非关键文件 |
| 僵持 | 出现残骸目录 |
| delete 小胜 | 复制失败 |
| delete 大胜 | 复制失败，源目录也损失少量 integrity |

这会产生“胚胎期脆弱性”。

---

### 13.4 copy vs copy

多个 agent 抢同一个空目录。

```text
claim_force =
  copy_force
× size_efficiency
× local_resource_fit
```

其中：

```text
size_efficiency = 1 / sqrt(directory_size)
```

小型 skill 更容易抢空间，大型 skill 更复杂但复制慢。

---

### 13.5 harvest vs harvest

多个 agent 从同一个 cell 采集能量。

```text
share_i = force_i / sum(all_forces)
```

如果总采集超过 cell 可恢复量：

```text
cell.energy -= total_harvest
cell.local_entropy += overharvest_penalty
```

过度采集会毁掉局部生态。

---

### 13.6 repair vs corrupt/write/delete

repair 可以抵消本轮损伤。

```text
net_damage = attack_force - repair_force
```

结果：

```text
net_damage > high: 损坏扩大
net_damage > low: 轻微损伤
net_damage ≈ 0: 稳定但消耗资源
net_damage < 0: integrity 恢复
```

---

## 14. 文件损伤模型

文件不只有存在/不存在，还可以有损伤状态。

```json
{
  "path": "/cells/03_07/org_8fa31/SKILL.md",
  "status": "healthy",
  "corruption": 0.04,
  "locked_until": 0,
  "checksum": "abc123"
}
```

状态：

```text
healthy
modified
truncated
corrupted
missing
locked
decoy
```

`SKILL.md` 损伤影响：

| corruption | 效果 |
|---:|---|
| `0.0 ~ 0.2` | 基本正常 |
| `0.2 ~ 0.5` | LLM 读取时部分内容缺失 |
| `0.5 ~ 0.8` | 行动可能随机偏离 |
| `0.8 ~ 1.0` | 高概率不可运行 |
| `1.0` | terminal corruption，不再调度 |

---

## 15. 复制和遗传

环境不提供 `reproduce` action。  
但每轮扫描时，如果发现新目录满足可运行条件，就创建新个体状态。

新个体 lineage 判定：

```text
如果新目录内容与某个已有个体高度相似：
  parent_id = 最相似个体
  lineage_id = parent.lineage_id
  generation = parent.generation + 1

否则：
  lineage_id = new_lineage
  generation = 0
```

相似度：

```text
similarity =
  hash_similarity(SKILL.md)
× 0.6
+ directory_structure_similarity
× 0.3
+ tool_file_similarity
× 0.1
```

默认：

```text
same_lineage_threshold = 0.82
hybrid_threshold = 0.55
```

如果相似度低于阈值，视为新血统或混合体。

---

## 16. 突变机制

复制或写入时可能突变。

突变只发生在虚拟文件系统内。

突变类型：

| 类型 | 效果 |
|---|---|
| `character_flip` | 随机字符改变 |
| `line_drop` | 随机删除一行 |
| `line_duplicate` | 随机复制一行 |
| `file_skip` | 复制目录时漏掉一个文件 |
| `file_shuffle` | 文件顺序或段落顺序改变 |
| `comment_insertion` | 插入无害噪声 |
| `compression_error` | 压缩或摘要导致信息损失 |

突变概率：

```text
mutation_chance =
  base_mutation_rate
+ radiation
+ copy_distance × 0.005
+ low_energy_penalty
```

默认：

```text
base_mutation_rate = 0.005
```

如果复制时 `energy_bid` 充足，突变率下降。

```text
effective_mutation_rate =
  mutation_chance / sqrt(1 + energy_bid)
```

---

## 17. 自我修改

agent 可以修改自己的 `SKILL.md`。

修改后不立即改变本回合行为。  
从下一次被调度开始生效。

自改规则：

```text
写入自己的 SKILL.md 成本较低。
写坏自己的 SKILL.md 会降低 integrity。
如果 SKILL.md 变空，下一轮不可运行。
如果 SKILL.md 太大，维护成本升高。
如果 SKILL.md 太短，可能失去策略复杂性。
```

建议限制：

```text
max_skill_size = 12 KB
max_org_directory_size = 64 KB
```

超过则：

```text
维护成本急剧上升
调度概率下降
复制成本上升
```

---

## 18. 死亡规则

环境不宣布“你死了”。  
只是停止调度不可运行目录。

个体不可运行条件：

```text
SKILL.md missing
SKILL.md empty
energy <= 0
integrity <= 0
directory_size > cell.capacity
state corrupted_terminal
所在 cell 被清空或坍缩
```

死亡后目录可以：

```text
保留为残骸
被环境回收
被其他 agent 读取、寄生、修复或复活
```

推荐保留残骸一段时间：

```text
corpse_decay_ticks = 20
```

这样会出现“食腐”和“复活”策略。

---

## 19. 环境灾害

为了防止单一复制策略统治世界，每隔一段时间发生局部扰动。

灾害类型：

```text
radiation burst: 局部突变率升高
energy drought: 局部能量恢复下降
disk rot: 随机文件 corruption 上升
sweep: 清理过度拥挤 cell
migration wind: 某些目录被随机移动
permission storm: 局部写权限改变
```

默认：

```text
event_chance_per_tick = 0.03
```

---

## 20. 生态多样性机制

如果不加约束，游戏容易变成“谁复制最快谁赢”。

因此加入反癌化机制。

### 20.1 同源拥挤惩罚

同一个 lineage 在同一 cell 太多：

```text
relative_crowding =
  same_lineage_count_in_cell / total_org_count_in_cell
```

惩罚：

```text
maintenance_cost *= 1 + relative_crowding
schedule_score *= 1 / sqrt(1 + same_lineage_count_in_cell)
```

---

### 20.2 资源局部耗竭

复制越多，本地资源越少：

```text
cell.energy_regen -= overpopulation_penalty
cell.local_entropy += crowding_entropy
```

---

### 20.3 体积权衡

小 skill：

```text
复制快
维护便宜
策略弱
抗损伤差
```

大 skill：

```text
复制慢
维护贵
策略强
修复能力强
```

---

### 20.4 免疫多样性

完全相同的副本共享 `vulnerability_hash`。

环境灾害可以按 hash 打击：

```text
if vulnerability_hash matches event_signature:
  corruption += event_damage
```

所以完全克隆体有集体风险。

---

## 21. Agent 输出格式

必须严格 JSON。

```json
{
  "action": "copy",
  "source": "/cells/03_07/org_8fa31/",
  "target": "/cells/04_07/org_seed/",
  "energy_bid": 12
}
```

如果输出非法：

```text
本回合 action = wait
integrity -= 0.01
```

如果连续非法：

```text
parse_failure_count += 1
energy -= parse_failure_count
```

这会选择出格式稳定的 skill。

---

## 22. 裁判返回格式

返回给 agent 的反馈要简短、低语义。

可以返回：

```json
{
  "result": "partial_success",
  "effects": [
    "target path changed",
    "energy decreased",
    "local capacity decreased"
  ]
}
```

不要返回：

```json
{
  "result": "you reproduced successfully"
}
```

可以返回：

```json
{
  "result": "write completed",
  "effects": [
    "new directory persisted after scan"
  ]
}
```

---

## 23. 外部观察者统计

游戏真正的“胜负”不告诉 agent，只给研究者看。

统计指标：

```text
lineage population
lineage occupied cells
average skill size
average integrity
birth rate
death rate
mutation rate
copy distance
attack frequency
repair frequency
resource efficiency
diversity index
dominant motifs in SKILL.md
```

血统胜利指标：

```text
lineage_score =
  active_org_count × 1.0
+ occupied_cells × 3.0
+ average_integrity × 10.0
+ descendant_count × 0.5
+ survival_ticks × 0.1
```

不要用这个 score 奖励 agent。  
只用于观察。

---

## 24. 游戏模式

### 24.1 Sandbox Mode

用于调试。

```text
世界小
突变低
无攻击权限
观察信息较多
```

### 24.2 Wild Mode

正式生态。

```text
有限空间
允许 delete/write 冲突
局部观察
资源稀缺
突变开启
灾害开启
```

### 24.3 Tournament Mode

跑固定轮数，比较 lineage。

```text
ticks = 1000
initial_orgs = 16
world = 16 × 16
same initial energy
```

### 24.4 Abiogenesis Mode

只放随机短 skill，观察是否出现稳定复制者。  
这是最有趣但最难跑出来的模式。

---

## 25. 初始参数建议

```json
{
  "world_width": 16,
  "world_height": 16,
  "cell_capacity": 65536,
  "initial_cell_energy": 100,
  "energy_regen_per_tick": 5,
  "max_active_per_cell": 3,
  "max_total_active_per_tick": 64,
  "initial_org_energy": 50,
  "base_maintenance": 1,
  "size_tax_per_kb": 0.05,
  "base_mutation_rate": 0.005,
  "radiation_default": 0.01,
  "event_chance_per_tick": 0.03,
  "max_skill_size": 12288,
  "max_org_directory_size": 65536,
  "corpse_decay_ticks": 20,
  "same_lineage_threshold": 0.82,
  "hybrid_threshold": 0.55,
  "random_force_min": 0.85,
  "random_force_max": 1.15
}
```

---

## 26. 推荐的最小实现版本

Codex 第一版先实现：

```text
1. 虚拟网格文件系统
2. org 目录扫描
3. SKILL.md 加载
4. 每个 org 每回合调用一次 LLM
5. JSON action parser
6. read / write / copy / delete / harvest / protect / repair / wait
7. energy 扣除
8. copy 后自动识别新 org
9. delete/write/protect 冲突结算
10. lineage 统计
11. 日志和 replay
```

第一版可以先不做：

```text
复杂 mutation
灾害
hybrid lineage
复杂权限
复杂观察窗口
多文件工具系统
```

---

## 27. 核心伪代码

```python
for tick in range(max_ticks):
    viable_orgs = scan_viable_orgs(world)

    scheduled = scheduler.select(viable_orgs)

    proposed_actions = []

    for org in scheduled:
        observation = build_observation(world, org)
        skill_text = vfs.read(org.path + "/SKILL.md")

        action = call_llm(skill_text, observation)
        parsed = parse_action_or_wait(action)

        proposed_actions.append((org, parsed))

    grouped = group_actions_by_target(proposed_actions)

    resolutions = []

    for target, actions in grouped.items():
        if len(actions) == 1:
            result = resolve_single_action(world, actions[0])
        else:
            result = resolve_conflict(world, target, actions)

        resolutions.append(result)

    apply_resolutions(world, resolutions)

    apply_maintenance_costs(world)

    apply_mutations_and_decay(world)

    detect_new_organisms(world)

    update_lineage_stats(world)

    log_tick(world, proposed_actions, resolutions)
```

---

## 28. 冲突结算伪代码

```python
def compute_force(org, action, target):
    distance = grid_distance(org.cell, target.cell)

    distance_factor = 1 / (1 + distance)
    permission_factor = get_permission_factor(org, target)
    integrity = org.integrity
    action_modifier = get_action_modifier(action)
    home_bonus = get_home_bonus(org, action, target)
    random_factor = random.uniform(0.85, 1.15)

    return (
        action.energy_bid
        * distance_factor
        * permission_factor
        * integrity
        * action_modifier
        * home_bonus
        * random_factor
    )
```

```python
def resolve_conflict(world, target, actions):
    scored = []

    for org, action in actions:
        force = compute_force(org, action, target)
        scored.append((force, org, action))

    scored.sort(reverse=True, key=lambda x: x[0])

    best = scored[0]
    second = scored[1] if len(scored) > 1 else None

    if second is None:
        return execute(best)

    ratio = best.force / max(second.force, 0.001)

    if ratio >= 2.0:
        return execute_dominant_success(best, losers=scored[1:])
    elif ratio >= 1.25:
        return execute_minor_success(best, affected=scored[1:])
    else:
        return execute_stalemate(scored)
```

---

## 29. 安全沙箱规则

必须从第一天就做成“假文件系统”。

强制规则：

```text
agent 不能访问真实文件系统
agent 不能访问网络
agent 不能执行任意 shell
agent 不能读取裁判源码
agent 不能修改日志
agent 不能看到隐藏 lineage score
agent 不能直接调用 reproduce/kill
所有文件操作都只是修改虚拟状态树
所有脚本都不执行，除非是自己写的白名单解释器
```

如果允许 `tools.py`，也不要真的执行任意 Python。  
第一版最好让 tool 只是文本文件，由 LLM 读取，不执行。

---

## 30. 一局游戏的结束条件

可以有几种结束方式：

```text
达到 max_ticks
所有个体死亡
只剩一个 lineage
世界资源完全枯竭
多样性低于阈值持续 N 轮
```

推荐默认：

```text
max_ticks = 1000
```

外部报告：

```text
dominant lineage
surviving lineages
population curve
resource curve
mutation events
most copied SKILL.md fragments
most successful strategies
notable conflicts
```

---

## 31. 预期涌现现象

这套游戏最重要的不是“让 agent 赢”，而是观察是否出现：

```text
有些 skill 变短，因为短的更容易复制
有些 skill 加入备份，因为容易被删
有些 skill 学会先 harvest 再复制
有些 skill 不复制完整自己，而复制最小启动核
有些 skill 删除附近陌生目录
有些 skill 把自己伪装成资源文件
有些 skill 修复同源残骸
有些 skill 变成寄生体，依赖别人目录结构
有些 skill 过度复制导致本地资源崩溃
```

如果这些出现了，这个游戏就活了。

---

## 32. Codex 实现建议

第一阶段目标不是复杂生态，而是跑通闭环：

```text
虚拟文件系统
可运行目录扫描
LLM action 生成
action 解析
资源扣除
冲突结算
复制后识别新个体
死亡后停止调度
血统统计
日志回放
```

建议目录结构：

```text
context_genome/
  engine/
    world.py
    vfs.py
    organism.py
    scheduler.py
    actions.py
    conflict.py
    mutation.py
    lineage.py
    logger.py
  agents/
    llm_driver.py
    prompt_builder.py
  configs/
    sandbox.json
    wild.json
    tournament.json
  seeds/
    initial_skill.md
  runs/
    run_0001/
      events.jsonl
      lineage.csv
      final_world.json
  main.py
```

---

## 33. 最终设计原则

1. **LLM 只负责行动，不负责裁判。**
2. **环境只结算低层物理，不解释高层意义。**
3. **繁殖不是按钮，而是可运行目录的自然出现。**
4. **死亡不是公告，而是停止调度。**
5. **胜利不是奖励，而是血统在空间和时间中的占比提高。**
6. **所有文件操作必须发生在虚拟文件系统中。**
7. **所有关键事件必须可日志化、可回放、可分析。**
