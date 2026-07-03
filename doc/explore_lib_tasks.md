# 自探索轨迹库 · 100 条任务全表(最初目标 → 反推任务)

> 来源:`osworld_explore_rollout.py` 全量跑(5 app × 20),`/data/hwt/OSWorld/explore_lib/`。
> **最初目标** = ② 提目标阶段 GPT-5.5 提的粗目标(发动机);**反推任务** = ⑤ 从首末屏+动作反推出的 achieved_task(约束式)。
> `—(未通过)` = 连贯门判 incoherent,无反推任务。合计 **89/100 coherent**。

## libreoffice_calc(18/20)

| # | 最初目标 | 反推任务 |
|---|---|---|
| 0 | 在 B 列把空白的 Level 单元格向下填充,把每个可见层级标签向下复制,使每个学生/科目行都有 Level 值。 | 填满 B 列第 2–30 行所有空白 Level 单元格,把已有层级标签向下延续,使每个学生/科目行都有 Level 值:第 2–6 行 Primary、第 7–18 行 Secondary、第 19–24 行 Intermediate、第 25–30 行 Advance。 |
| 1 | 工作簿加载完成后,给已有表头行设置加粗文字和彩色背景,让 SalesRep 表标题突出。 | 给 SalesRep 表已有表头行 A1:G1 设置加粗文字和黄/橙色背景,使标题突出。 |
| 2 | 损益表工作簿加载后,选中跨日期列的营收行和净利润行,在工作表上插入标题为 “Revenue vs Net Income” 的折线图。 | —(未通过) |
| 3 | 用已有的 Year、CA Change、FA Change、OA Changes 数据创建折线图,对比 2015 到 2019 年三条百分比变化趋势。 | 用已有 Year、CA Change、FA Change、OA Changes 数据(2015–2019)创建折线图,对比三条百分比变化系列,标题为 “Percentage Change Trends 2015-2019”。 |
| 4 | 在 Jun 后新增 Total 列,用 SUM 公式计算每个销售代表 Jan–Jun 的销售总额,并向下填充所有列出的代表。 | 在 Jun 后新增 Total 列,为第一个销售代表输入 SUM 公式,汇总该行 Jan–Jun 的数值。 |
| 5 | 用已有的 Customer 和 Old ID 列,在 D 列用公式给 Old ID 补前导零生成每位客户的 7 位新 ID,并向下填充所有可见客户行。 | —(未通过) |
| 6 | 对已有的 Free/Paid 列应用条件格式,任何含 “Paid” 的单元格用红色背景高亮,使付费资源在评估清单中突出。 | 对 Free/Paid 列区域应用条件格式,含 “Paid” 的单元格用红色背景高亮。 |
| 7 | 在 COGS 后新增 Gross Profit 列,用公式计算每周的 Sales 减 COGS,并向下填充到 Week 10。 | 在 COGS 后新增 Gross Profit 列,Week 1 到 Week 10 每行值为对应行的 Sales 减 COGS。 |
| 8 | 在已有 Revenue 数据旁新增一个小汇总表,标注 Average、Maximum、Minimum revenue,并用公式从 A2:A20 计算这些值。 | 在已有数据旁新增汇总表,含 Metric 和 Revenue 两列,列出从已有 Revenue 值计算的 Average、Maximum、Minimum。 |
| 9 | 用最优列宽调整已有联系人表(C 到 H 列)的列宽,使 Name、Occupation、City、Email 值完整显示而非被截断。 | 把已有联系人表 C 到 H 列调整为最优宽度,使 ID、Name、Age、Occupation、City、Email 完整显示而非被截断。 |
| 10 | 在 Sales 后新增 Commission 列,用已有 Sales 值给每条发票行计算 5% 佣金,向下填充公式,并把结果设为货币格式。 | 在 Sales 紧邻右侧新增 Commission 列,每条发票行为其 Sales 值的 5%,以货币格式显示。 |
| 11 | 在 F 列新增 Future Value 列,用 FV 公式结合已有现值、年数、年利率、复利期数计算四笔投资各自终值,并把结果设为货币格式。 | 在 “# Compound Periods” 列紧邻右侧新增一个标为 “Future Value” 的列。 |
| 12 | 在 Marks 旁新增 Result 列,用 IF 公式把每行标为 Pass(分≥50)或 Fail(分<50),并向下填充所有可见学生/科目行。 | 在 Marks 紧邻右侧新增一列,表头为 “Result”。 |
| 13 | 把已有销售代表行(A2:G11)按 Jun 销售列降序排序,使六月最高业绩者在最上方,同时保留表格下方的 Total 和 Growth 行。 | 把已有销售代表行按 Jun 销售列降序排序,保持下方 Total 和 Growth 行不变。 |
| 14 | 用公式补全损益表:Net Sales = Sales 减 Sales Return 减 Discounts and Allowances;Total Cost of Goods Sold = Materials Charges 加 Labor Charges 加 Overhead;Gross Profit = Net Sales 减 Total Cost of Goods Sold,覆盖 2015–2023 各年。 | 填 2015–2023 年 Net Sales = Sales 减 Sales Return 减 Discounts and Allowances,并填 2015–2022 年 Total Cost of Goods Sold = Materials Charges 加 Labor Charges 加 Overhead。 |
| 15 | 对已有 B2:D6 百分比变化数据应用条件格式,所有负值用浅红背景高亮,使下降一目了然。 | 对已有 2015–2019 百分比变化表应用条件格式,CA Change、FA Change、OA Changes 列中所有负值用浅红背景高亮。 |
| 16 | 在 Jun 后新增 Average 列,用 AVERAGE 公式计算每个销售代表 Jan 到 Jun 的月均销售,向下填充所有可见代表,并把均值设为保留一位小数。 | 在 Jun 后新增 Average 列,计算每个可见销售代表 Jan 到 Jun 的平均销售,所有可见代表结果保留一位小数。 |
| 17 | 把已有客户表(B1:D30)按 Old ID 列升序排序,使客户从最小 ID 到最大 ID 排列,同时每个客户名与其 ID 保持匹配。 | 把客户表按 Old ID 列升序排序,每个客户名与其对应 ID 保持匹配。 |
| 18 | 对已有评估资源表开启 AutoFilter,并把 Free/Paid 列筛选为只显示标为 “Free” 的资源,便于查看免费选项。 | 只显示 Free/Paid 列标为 “Free” 的评估资源记录,并在已有表头启用筛选。 |
| 19 | 用已有的 Week、Sales、COGS 数据(A1:C11)创建柱状图,直观对比第 1–10 周的销售与成本。 | 用第 1–10 周的 Week、Sales、COGS 数据创建柱状图,x 轴为 Week 标签,Sales 与 COGS 分为两个系列以便对比。 |

## libreoffice_writer(18/20)

| # | 最初目标 | 反推任务 |
|---|---|---|
| 0 | 把已有文档的开头段落设为加粗、居中的引言,使其从其余正文中突出。 | 把文档开头段落设为加粗、居中的引言,其余正文保持不变。 |
| 1 | 把已有的分步说明转换为编号列表,使 eBook 设置流程更清晰、有序。 | 把 “How to use BLCUP eBook for PC” 下的五条设置说明设为从 1 到 5 的有序编号列表,保留其原文。 |
| 2 | 在事实表底部附近插入一个简单的两列表格,把联系方式整理为标签和值,例如 Address、Phone、Website、Media enquiries。 | 在事实表底部附近新增两列联系方式表格,第一行标签为 “Address”,对应值为 “King Edward Terrace Canberra”。 |
| 3 | 在那张大的 LibreOffice 图片下方加一个居中图注 “LibreOffice Writer overview”,并设为斜体,以清晰标注该图。 | 在那张大的 LibreOffice 图片正下方加一个居中、斜体的图注 “LibreOffice Writer overview”。 |
| 4 | 在文档顶部加标题 “Dublin Zoo Introduction”,设为大号加粗标题,置于已有正文上方。 | 在文档顶部、已有正文上方加一个大号标题 “Dublin Zoo Introduction”。 |
| 5 | 把已有条款表的表头行填为浅灰色,并把列标题加粗,以提升可读性。 | —(未通过) |
| 6 | 用淡黄色背景高亮已有文档中的 “Navigation:” 说明行,使菜单路径更易找到。 | 用黄色背景高亮已有的 “Navigation:” 菜单路径行,使其在文档中突出。 |
| 7 | 把联系方式部分中已有的网址变成可点击的超链接,使读者能直接从文档打开 Dublin Zoo 网站。 | —(未通过) |
| 8 | 用查找替换把招募电话脚本中每处高亮占位符 “UCSF” 替换为具体研究站点名,例如 “Bay Area Research Center”。 | 把招募电话脚本中每处高亮占位符 “UCSF” 替换为 “Bay Area Research Center”,保留周围脚本内容。 |
| 9 | 把已有的逗号分隔火车记录行用逗号作分隔转换为 4 列表格,再加一个表头行,标注 Time、Train ID、Category、Count,使数据更易读。 | 把逗号分隔的火车记录行转换为四列表格,字段分为 Time、Train ID、Category、Count,并加一个表头行,分别标注 “Time”、“Train ID”、“Category”、“Count”。 |
| 10 | 在已有大纲顶部加一个清晰的课程标题,例如 “GEOG2169 Course Outline”,并设为居中加粗标题,置于当前引言正文上方。 | 在已有引言正文上方加标题 “GEOG2169 Course Outline”,并设为居中加粗标题。 |
| 11 | 从 dock 打开 LibreOffice Writer,新建空白文档,输入一则标题为 “Ubuntu Desktop Notes” 的短笔记(含可见日期 “Jul 3”),并在 Home 文件夹存为 Writer 文档。 | 创建并保存 Writer 文档 “Ubuntu Desktop Notes.odt”,含标题 “Ubuntu Desktop Notes”、一行 “Date: Jul 3” 和一句备注 “This is a short note created in LibreOffice Writer on the Ubuntu desktop.”。 |
| 12 | 新建标题为 “Ubuntu Launcher Inventory” 的 Writer 文档,列出若干可见 dock 应用(如 Chrome、Thunderbird、VS Code、VLC、LibreOffice),然后存到 Home 文件夹。 | 创建并保存 Writer 文档 “Ubuntu Launcher Inventory.docx”,含标题 “Ubuntu Launcher Inventory” 和一个 “Visible dock applications:” 小节,列出 Chrome、Thunderbird、VS Code、VLC、LibreOffice Writer、LibreOffice Calc、LibreOffice Impress。 |
| 13 | 打开正在运行的 LibreOffice Writer 窗口,新建标题为 “Ubuntu Jellyfish Wallpaper” 的短文档,写两句描述可见的紫色水母桌面背景,并在 Home 文件夹存为 Writer 文档。 | 创建并保存 Writer 文档 “Ubuntu Jellyfish Wallpaper.odt”,含标题 “Ubuntu Jellyfish Wallpaper” 和对紫色水母 Ubuntu 桌面背景的简短描述(暗色渐变、发光触须、紫罗兰色、宁静未来感如海洋般的氛围)。 |
| 14 | 在已有文档顶部加一个加粗、居中的标题 “What Makes a Novel Different?”,引出可见的关于小说特征的讨论。 | 在文档顶部、已有讨论正文前加一个加粗、居中的标题 “What Makes a Novel Different?”。 |
| 15 | 把可见的支持联系行 “service blcup.com” 改为 “service@blcup.com”,并设为可点击的邮件超链接,便于获取支持。 | 把可见的支持联系行改为 “Support Contact: service@blcup.com”,并把该邮箱地址设为可点击的邮件超链接。 |
| 16 | 在事实表底部的地址、电话、网址上方加一个加粗小标题 “Visitor details”,把联系信息与主展览描述分开。 | 在事实表底部联系信息小节前紧邻加一个加粗小标题 “Visitor details”,把它与主展览描述分开。 |
| 17 | 删除 “Lulu Self-Publishing” 和 “Follow” 文字下方那些散乱的单字符行(孤立的句点和 “25”),使引言页在那张大 LibreOffice 图片前更整洁。 | 清理引言页,删除那张大 LibreOffice 图片上方的孤立句点行和孤立的 “25”。 |
| 18 | 把第二段中 “london Zoo” 改为 “London Zoo”,修正大小写错误,使编辑后的历史文字准确、规范。 | 把第二段 “london Zoo” 改为 “London Zoo” 以修正大小写,同时保留周围 Dublin Zoo 历史文字不变。 |
| 19 | 把已有条款表的表头行(#、Clause、Purpose)设为在后续页面顶部重复,使这张很长的章程指引表在分页处仍可读。 | 配置已有章程指引条款表,使其含 “#”、“Clause”、“Purpose” 的表头行在后续页面顶部重复。 |

## libreoffice_impress(14/20 · 最弱)

| # | 最初目标 | 反推任务 |
|---|---|---|
| 0 | 在当前幻灯片加一个小文本框,内容为可见的演示文件名作为页脚标签,然后保存演示。 | ⚠️ 末态未见连贯的演示编辑。 |
| 1 | 打开文档 Properties 对话框,把演示 Title 字段设为可见文件名 “05dd4c1d_38_1_Gold_all_fonts.pptx”,然后保存。 | —(未通过) |
| 2 | 删除遮住幻灯片要点文字的灰色条纹矩形,使定义可读,然后保存演示。 | 删除遮住幻灯片要点定义的灰色条纹矩形使文字完全可读,并保存演示。 |
| 3 | 打开演示 Properties 对话框,基于可见文件名 “0a211154_13_0_Gold.pptx” 把 Subject 字段设为 “Gold presentation”,然后保存。 | —(未通过) |
| 4 | 把主幻灯片标题 “Button Style Podium” 设为蓝色字体使其突出,然后保存演示。 | 把幻灯片上 “Button Style Podium” 标题文字设为蓝色字体并保存演示。 |
| 5 | 用已有标题和要点占位符做一张简单封面页:标题设为 “Original Presentation”,加一条要点 “Source file: 15aece23_134_2_Original.pptx”,然后保存。 | 把第一张幻灯片标题设为 “Original Presentation”,保留已有正文占位符不变。 |
| 6 | 新建一张标题页,用可见的应用名作内容:标题设为 “LibreOffice 7.3”,加副标题 “Presentation created in Impress”,然后保存。 | 创建并保存一张新的演示幻灯片,标题 “LibreOffice 7.3”,副标题 “Presentation created in Impress”。 |
| 7 | 把 slide 2 已有的紫色主题应用到 slide 1,即把 slide 1 背景色设为紫色,然后保存。 | 把 slide 1 背景设为与演示所用紫色主题相配的纯紫/靛色,并保存演示。 |
| 8 | 编辑当前幻灯片上碎裂的大标题文字,使其在顶部清晰读作 “NEW PRODUCT LAUNCH”,删除或修正残缺的标题片段,然后保存。 | 把当前幻灯片左上角标题文字设为第一行 “NEW PRODUCT”、第二行 “LAUNCH”。 |
| 9 | 新建一张空白演示幻灯片,加一个大号居中文本框读作 “LibreOffice 7.3”(取自可见窗口标题),文字加粗,然后保存。 | 创建一张单页空白演示,含一个居中加粗文本框读作 “LibreOffice 7.3”。 |
| 10 | 把 slide 1 上的灰色条纹图片从左上区域移到右上角,使其不再与要点文字争位,然后保存。 | 在 slide 1 上把灰色条纹图片放到幻灯片右上区域、远离要点文字,并保存演示。 |
| 11 | 打开演示 Properties 对话框,基于可见文件名把 Subject 字段设为 “GUI events lecture”,然后保存。 | —(未通过) |
| 12 | 打开演示 Properties 对话框,基于可见文件名把 Keywords 字段设为 “project plan, one-page, WSSF”,然后保存。 | —(未通过) |
| 13 | 用可见的桌面信息新建 Impress 标题页:标题设为 “Soffice”,副标题设为 “Jul 3 08:03”,然后保存。 | 保存演示,含一张标题页:标题 “Soffice”,副标题 “Jul 3 08:03”。 |
| 14 | 修正当前幻灯片上碎裂的标题文字,使其清晰读作 “NEW PRODUCT LAUNCH PROPOSAL”,替换分离的片段,然后保存。 | 保存演示,当前幻灯片化简为纯蓝底,含单一清晰标题文本框、顶部附近读作 “NEW PRODUCT LAUNCH PROPOSAL”。 |
| 15 | 打开文档 Properties 对话框,基于可见文件名 “05dd4c1d_38_1_Gold_all_fonts.pptx” 把 Keywords 字段设为 “Gold, fonts”,然后保存。 | 把演示文档的 Keywords 元数据设为 “Gold, fonts”,并确保文件已保存。 |
| 16 | 打开文档 Properties 对话框,基于可见文件名 “08aced46_22_6_Gold2.pptx” 把 Title 字段设为 “Gold2”,然后保存。 | 把演示文档属性的 Title 字段设为 “Gold2” 并保存演示。 |
| 17 | 打开演示 Properties 对话框,基于可见文件名把 Title 字段设为 “Gold”,然后保存。 | —(未通过) |
| 18 | 打开演示 Properties 对话框,基于可见文件名把 Title 字段设为 “Multimedia Classroom Podium 2020”,然后保存。 | —(未通过) |
| 19 | 把 slide 1 从当前空白式版式改为 标题+内容 版式,输入标题 “Original File Overview”,加两条要点 “Filename: 15aece23_134_2_Original.pptx” 和 “Slides: 2”,然后保存。 | 把 slide 1 更新为含标题 “Original File Overview” 和一个含 “Filename: 15aece23_134_2_Original.pptx” 与 “Slides: 2” 的要点列表,然后保存演示。 |

## gimp(19/20)

| # | 最初目标 | 反推任务 |
|---|---|---|
| 0 | 把导入的 gate.jpeg 从其内嵌 sRGB IEC61966-2.1 配置转换为 GIMP 内置 sRGB 工作空间,保持开启黑点补偿,然后导出/保存使色彩配置转换被持久化。 | 把 gate JPEG 从其内嵌 sRGB IEC61966-2.1 配置转换为 GIMP 内置 sRGB 配置(开启黑点补偿),并导出该 JPEG 使转换后的配置被持久化。 |
| 1 | 保留内嵌色彩配置以导入显示的 computer PNG,然后在图片底部附近加一个可见文字标签 “Computer”,并导出编辑后的 PNG 使标签被保存。 | 编辑 computer PNG,使其保留内嵌 sRGB 色彩配置,含底部附近一个可见文字标签 “Computer”,并导出保存该标签。 |
| 2 | 导入带背景的 dog PNG,用已选好的固定 1:1 比例裁剪工具把图片裁成以狗为中心的正方形,并导出裁剪后的 PNG 使新构图被保存。 | ⚠️ 在 GIMP 中打开带背景的 dog PNG 并把其内嵌色彩配置转换为内置 sRGB 工作空间,1578×948 全图保持不变(即未裁剪)。 |
| 3 | 保留或转换 panda.jpeg 的内嵌配置,然后用 Colors > Desaturate 把熊猫照片变为灰度图,并导出使黑白版本被保存。 | 把 panda JPEG 转换为内置 sRGB 配置,把照片变为灰度/去色的黑白图,并导出编辑后的 JPEG 使保存文件含灰度版本。 |
| 4 | 用裁剪工具对打开的坐着的女人照片做更紧凑的人像构图,去掉左侧大部分暗色旁人和右侧米色柱子,然后应用裁剪并导出使新取景被保存。 | —(未通过) |
| 5 | 用 Colors > Brightness-Contrast 对打开的 heron 照片略增对比、提亮水面上的鸟,以增强照片,然后导出编辑后的 JPEG 使改善的影调被保存。 | 通过把亮度和对比都提高到 +15 来增强 heron 照片,然后把编辑结果导出为 JPEG,含改善的影调。 |
| 6 | 在已有的透明机械臂 logo 后加一个纯深蓝背景图层,使白色 logo 突出,然后把图片导出为 PNG 并保留新背景。 | 把机械臂 logo 导出为 PNG,在已有 logo 图形后用纯深蓝(#001a4d)背景填满画布。 |
| 7 | 用裁剪工具对打开的结霜浆果照片去掉一些空天空和边缘杂物,围绕主要红色浆果簇做更紧凑构图,然后应用裁剪并导出使新取景被保存。 | 把结霜红浆果照片裁为更紧凑的 900×705 构图、以主要红浆果簇为中心,去掉周围空天空和边缘杂物。 |
| 8 | 用 Colors > Colorize 工具在图标图层上把已有黑色 “add user” 图标重新着色为亮蓝色,然后导出编辑后的 PNG 使新的蓝色图标被保存。 | ⚠️ 未完成连贯的图像编辑;图标仍为白底黑色,未见导出的蓝色 PNG。 |
| 9 | 对打开的 book-cover 图片应用 Filters > Enhance > Sharpen(Unsharp Mask),使标题和作者文字更清晰,然后导出编辑后的 JPEG 使锐化被持久化。 | 锐化打开的《The Lost River of Dreams》(作者 Sonia Beauchamp)封面 JPEG,使标题和作者文字更清晰,并把编辑结果持久化为导出的 JPEG 文件。 |
| 10 | 对打开的坐着的女人照片应用轻微暗角效果,使边缘变暗、注意力集中到她的脸,然后导出编辑后的图片以持久化效果。 | 对坐着的女人照片应用并导出暗角编辑,边缘变暗/发黑形成椭圆聚光,使女人的脸和上半身相对明亮、聚焦。 |
| 11 | 用 Colors > Hue-Saturation 增强打开的结霜浆果照片,提升红浆果饱和度、同时让结冰枝条和蓝天基本自然,然后导出编辑后的 JPEG 使更浓的浆果色被保存。 | 增强结霜浆果 JPEG,使红浆果显得更浓饱和,然后把编辑后的图片导出为保存的 JPEG 文件。 |
| 12 | 保留内嵌 sRGB 配置以导入 gate.jpeg,然后用已选好的固定 1:1 比例裁剪工具做以门为焦点的正方形裁剪,应用裁剪并导出编辑后的 JPEG 使新构图被保存。 | 为 gate.jpeg 保留内嵌 sRGB 配置,并导出一张裁为含门的 624×568 构图的编辑 JPEG。 |
| 13 | 保留内嵌 sRGB 配置以导入显示的 computer PNG,然后应用 Filters > Light and Shadow > Drop Shadow 在电脑图形后加轻微阴影,并导出编辑后的 PNG 使阴影被保存。 | 导出 computer PNG,保留内嵌 sRGB IEC61966-2.1 色彩配置,并在图片后加一个轻微 Drop Shadow 图层。 |
| 14 | 转换带背景 dog PNG 的内嵌配置,然后用 Image > Scale Image 把它缩放到当前宽高的 50%,并导出缩放后的 PNG 使较小版本被保存。 | 产出带背景 dog 图片的导出 PNG,已转换为内置 sRGB 色彩配置并缩放到 789×474 像素,即原尺寸的一半。 |
| 15 | 转换 panda.jpeg 的内嵌配置,然后应用 Filters > Artistic > Cartoon 给熊猫照片加风格化墨线描边效果,并导出编辑后的 JPEG 使卡通效果被保存。 | 把 panda JPEG 转换为内置 sRGB/RGB 色彩空间并对照片应用风格化卡通墨线描边效果后导出。 |
| 16 | 对打开的坐着的女人照片用 Colors > Color Balance 增加红/黄调略微暖化图片,然后导出编辑后的照片使更暖的色调被保存。 | 对坐着的女人照片应用轻微更暖的色彩平衡(增加红、黄调)后导出。 |
| 17 | 在打开的 heron 照片左下角加一个小的半透明文字水印 “Heron”,然后导出图片使水印被保存。 | 在 heron 照片左下角加一个半透明白色文字水印 “Heron”,并导出图片保存该水印。 |
| 18 | 用 Colors > Colorize 对已有机械臂 logo 把白/灰色臂染成明显的青色、同时保留透明,然后导出编辑后的 PNG 使重新着色的 logo 被保存。 | 把已有透明机械臂 logo 重新着色,使白/灰色臂染成明显的浅青色、同时保留透明背景,并保存/导出编辑后的 PNG。 |
| 19 | 应用 Filters > Light and Shadow > Lens Flare 在打开的浆果照片左上结霜枝条附近加一个轻微阳光反光效果,然后导出编辑后的 JPEG 使加入的冬日闪光被保存。 | 在浆果照片左上结霜枝条附近加一个轻微镜头光晕阳光反光效果,并把编辑后的图片导出为 JPEG 文件。 |

## vs_code(20/20)

| # | 最初目标 | 反推任务 |
|---|---|---|
| 0 | 用查找替换把打开文档中每处 “text” 替换为 “assessment”,然后保存文件。 | 把打开文档中每处字符串 “text” 替换为 “assessment” 并保存文件。 |
| 1 | 把已有 VS Code 设置 JSON 改为禁用自动换行,即把 `editor.wordWrap` 从 `wordWrapColumn` 改为 `off`,然后保存文件。 | 设置 VS Code 设置 JSON,使其含禁用工作区信任的设置、保持 `editor.wordWrapColumn` 为 50、并把 `editor.wordWrap` 设为 `off`。 |
| 2 | 在已有 settings.json 中插入 `"files.autoSave": "afterDelay"` 新增设置以启用自动保存,确保逗号仍合法,然后保存文件。 | 更新已有 settings.json,使其仍是合法 JSON,并在已有设置旁含 `"files.autoSave": "afterDelay"`,然后保存文件。 |
| 3 | 修改已有 Python 脚本,使 `hello_world()` 打印个性化问候(如 `Hello, Ubuntu user!`)而非 `Hello, world!`,然后保存文件。 | 更新 Python 脚本,使 `hello_world()` 打印 `Hello, Ubuntu user!`,且 main 保护块调用 `hello_world()`,并保存文件。 |
| 4 | 修改打开的 Python 脚本,通过在置信区间计算后加一条 `print(confint)` 使其自举结果可见,然后保存文件。 | 更新 Python 脚本,使其在计算 `confint = np.percentile(means, [2.5, 97.5])` 后通过加 `print(confint)` 输出置信区间,并保存文件。 |
| 5 | 更新打开的 settings.json,使 VS Code 删除文件前确认:在已有工作区信任设置后加 `"explorer.confirmDelete": true`,保持 JSON 合法,然后保存文件。 | 更新设置 JSON,使其仍合法,并在已有工作区信任设置后含 `"explorer.confirmDelete": true`。 |
| 6 | 把已有 VS Code 设置 JSON 改为使用 Light+ 主题,即把 `workbench.colorTheme` 从 `Visual Studio Dark` 改为 `Default Light+`,然后保存文件。 | 更新设置 JSON,使 `workbench.colorTheme` 设为 `Default Light+` 而非 `Visual Studio Dark`。 |
| 7 | 在打开的 settings.json 中插入 `"editor.fontSize": 16` 新增设置以增大编辑器字号,保持 JSON 合法,然后保存文件。 | 更新 settings.json 内容,含已有工作区信任设置,并加一个值为 16 的 `editor.fontSize` 设置。 |
| 8 | 修正已有 `python.analysis.diagnosticSeverityOverrides` 设置中畸形的 JSON:把 `"reportMissingImports": "none"` 放进 overrides 对象、置于 `"reportAssertTypeFailure": "none"` 之后,删掉多余花括号使红色语法错误消失,然后保存设置文件。 | 在已有 `python.analysis.diagnosticSeverityOverrides` 块内加一个值为 `none` 的 `reportMissingImports` 项,同时保留工作区信任设置。 |
| 9 | 在打开的 keybindings.json 中新增一条自定义快捷键项,把 `ctrl+alt+f` 映射到命令 `editor.action.formatDocument`、条件为 `editorTextFocus`,保持 JSON 数组合法,然后保存文件。 | 新增并保存一条 keybindings JSON 项,把 `ctrl+alt+f` 映射到 `editor.action.formatDocument`、条件为 `editorTextFocus`,保持数组结构合法。 |
| 10 | 用查找替换把打开文本文件中每处 “curriculum” 替换为 “program”,然后保存文件。 | 把打开文本文件中每处 “curriculum” 替换为 “program” 并保存更新后的文件。 |
| 11 | 在打开的 settings.json 中插入 `"editor.minimap.enabled": true` 新增设置以启用小地图渲染,保持 JSON 合法,然后保存文件。 | 更新打开的 VS Code 设置 JSON,含 `"editor.minimap.enabled": true`,同时保持 JSON 合法并已保存。 |
| 12 | 在打开的 settings.json 中插入 `"editor.bracketPairColorization.enabled": true` 新增设置以启用括号对着色,保持 JSON 合法,然后保存文件。 | 在 settings.json 加设置 `"editor.bracketPairColorization.enabled": true`,保持 JSON 合法并保存文件。 |
| 13 | 重构打开的 Python 脚本,使 `hello_world` 接受 `name` 参数、打印如 `Hello, VS Code!` 的 f-string 问候,把调用改为 `hello_world("VS Code")`,然后保存文件。 | 重构 Python 脚本,使 `hello_world` 接受 `name` 参数、用 f-string 打印 `Hello, {name}!`,且 main 块调用 `hello_world("VS Code")`。 |
| 14 | 修改打开的 Python 脚本,通过在 `import numpy as np` 后紧接加 `np.random.seed(42)` 使随机自举可复现,然后保存文件。 | 更新 Python 脚本,使其在 `import numpy as np` 后紧接把 NumPy 随机种子设为 42,使后续随机自举计算可复现,并保存改动。 |
| 15 | 在打开的 settings.json 中插入 `"editor.minimap.enabled": false` 新增设置以隐藏编辑器小地图,保持 JSON 合法,然后保存文件。 | 更新设置 JSON,含一个合法的新设置 `"editor.minimap.enabled": false`,同时保留已有工作区信任设置。 |
| 16 | 在打开的 settings.json 中插入 `"telemetry.telemetryLevel": "off"` 新增设置以禁用遥测,保持 JSON 合法,然后保存文件。 | 在已有设置 JSON 加 VS Code 设置 `"telemetry.telemetryLevel": "off"`,保持 JSON 语法合法并保存文件。 |
| 17 | 在打开的 settings.json 中插入 `"editor.wordWrap": "on"` 新增设置以启用自动换行,保持 JSON 合法,然后保存文件。 | 更新打开的 settings.json,使其仍是合法 JSON,并在已有工作区信任设置旁含 `"editor.wordWrap": "on"`。 |
| 18 | 在打开的 settings.json 中插入 `"update.mode": "none"` 新增设置以禁用自动更新提示,保持 JSON 合法,然后保存文件。 | 更新 VS Code 设置 JSON,使其仍合法,并在已有工作区信任和 Python 诊断覆盖设置旁含 `"update.mode": "none"`,然后保存。 |
| 19 | 恢复普通文本编辑器的 Ctrl+F:删除解绑 `actions.find` 的第一个 keybinding 对象,保留 notebook 专用项、保持 JSON 合法,然后保存 keybindings.json。 | 更新 keybindings.json 为合法已保存 JSON,只含针对 `-notebook.find` 的 Ctrl+F notebook 专用解绑(带 interactive/notebook 编辑器 when 条件),删掉 editor-focused 的 `-actions.find` 解绑,使 Ctrl+F 在普通文本编辑器中仍可用。 |
