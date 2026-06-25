# mmskill_example — 一个 skill 一个文件夹(v2 · 2026-06-25)

> 配套 `../CLAUDE.md`(v5) §2 三层定义
> 全部由 **gpt-5.5 从纯视频自动提取**(均匀抽帧、无任务说明、无 action_log;锚点 bbox 由 VLM 自己框)。
> v2 已去掉拼接的 long_video(那是人工拼的,有跨任务边界 artifact),并应用质检后的修复。

## 分类(共 15 个 skill)
- `gui/`(10):OnlyOffice / PDFedit 操作(切 Forms / 插复选框 / 插下拉 / 翻页删页 / 插图 / 插文字)
- `minecraft/`(5):游戏 skill(沙漠移动 / 进砂岩凹陷 / 钻低矮通道 / 看地下空间)

## 每个 skill 文件夹
```
<category>/<NN_skillname>/
  skill.json              三层:context(情境)/anchors(锚点)/procedure(流程,每步带 expect)
  context_fullframe.jpg   情境·整帧(取"状态刚出现"的入口帧)
  anchors/<role>.jpg      锚点·局部(只放"要操作的元素",bbox 加了 padding 带上下文)
```

## v2 应用的修复(对应质检发现)
- **① bbox 加 padding**:锚点图外扩带上下文,不再裁成空白小块。
- **③ cue_frame 取"入口帧"**:情境 = "该用这个 skill 的时机"(对话框刚弹出),不是动作做一半。
- **④ anchors 只放操作对象**:要点/输入/瞄准的元素才进 anchors;"动作产生的结果/核验"(插入后的复选框、变化后的页码)进 `procedure[].expect` 文字,不再当锚点。

## 怎么看(gui/02 为例)
- `context_fullframe.jpg` = 整帧(Forms 激活、文档还空着的入口态);
- `anchors/checkbox_button.jpg` = 局部(Checkbox 按钮 + 带上下文);
- `skill.json`:anchors 只有 `checkbox_button`;"第1项后出现小方框"写在 procedure 的 `expect`(核验)。

## 已知待解
- **Minecraft 世界物体**(同类方块外观相同)的 bbox 仍会框歪(如 `cactus_landmark` 裁到天空)——纯 VLM bbox 不够,需 `space:世界` + 相对位置(对应四步里的「对齐」)。
- `sig`(检索嵌入)、`space`、embedding 未做——服务「检索/对齐」两步,后续补。
