#!/usr/bin/env python3
"""Generate 李亚飞 Resume PDF - STAR Enhanced Version"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

pdfmetrics.registerFont(TTFont('Hei', '/System/Library/Fonts/STHeiti Medium.ttc'))
pdfmetrics.registerFont(TTFont('Song', '/System/Library/Fonts/Supplemental/Songti.ttc'))

# Black + Blue professional palette
BLUE    = HexColor('#2563eb')
DARK    = HexColor('#1a1a2e')
GRAY    = HexColor('#6b7280')
LGRAY   = HexColor('#f3f4f6')
BORDER  = HexColor('#d1d5db')
WHITE   = white

PAGE_W, PAGE_H = A4
M = 16 * mm

def S(name, **kw):
    defaults = dict(fontName='Hei', leading=12)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)

title_s   = S('title',   fontName='Hei', fontSize=20, textColor=DARK, spaceAfter=2, leading=24)
sub_s     = S('sub',     fontName='Hei', fontSize=10, textColor=BLUE, spaceAfter=2)
meta_s    = S('meta',    fontName='Hei', fontSize=8.5, textColor=GRAY, spaceAfter=1)
sec_s     = S('sec',     fontName='Hei', fontSize=11, textColor=BLUE, spaceBefore=8, spaceAfter=3, leading=14)
company_s = S('company',  fontName='Hei', fontSize=10, textColor=DARK, spaceAfter=1, leading=13)
role_s    = S('role',    fontName='Hei', fontSize=9,  textColor=BLUE, spaceAfter=1, leading=12)
period_s  = S('period',  fontName='Hei', fontSize=8,  textColor=GRAY, spaceAfter=3, leading=11)
bullet_s  = S('bullet',  fontName='Hei', fontSize=8.5, textColor=GRAY, spaceAfter=2, leading=12, leftIndent=14, firstLineIndent=-12)
sklabel_s = S('sklabel', fontName='Hei', fontSize=8,  textColor=GRAY, leading=11)
tag_s     = S('tag',     fontName='Hei', fontSize=8,  textColor=DARK, leading=11)
school_s  = S('school',  fontName='Hei', fontSize=10, textColor=DARK, spaceAfter=1)
major_s   = S('major',   fontName='Hei', fontSize=9,  textColor=GRAY, spaceAfter=1)
honor_s   = S('honor',   fontName='Hei', fontSize=9,  textColor=DARK, spaceAfter=2, leading=12)
star_lbl  = S('slbl',   fontName='Hei', fontSize=8,  textColor=BLUE, spaceAfter=1, leading=11)
star_txt  = S('stxt',   fontName='Hei', fontSize=8.5, textColor=GRAY, spaceAfter=3, leading=12)

W = PAGE_W - 2 * M
output = os.path.join(os.path.dirname(__file__), '..', 'static', 'about', 'resume.pdf')
output = os.path.abspath(output)

doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=M, rightMargin=M, topMargin=M, bottomMargin=M)
story = []

# ── Header ─────────────────────────────────────────────────────
av_w = 18 * mm
header_data = [[
    Paragraph('李', S('av', fontName='Hei', fontSize=26, textColor=WHITE, alignment=1, leading=30)),
    [Paragraph('李亚飞', title_s),
     Paragraph('四年经验 · 后端开发工程师 · 北京', sub_s),
     Paragraph('17603444963  |  liyafei.work@foxmail.com  |  github.com/RaphaelL2e', meta_s)],
]]
ht = Table(header_data, colWidths=[av_w, W - av_w])
ht.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, -1), LGRAY),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 10),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ('LEFTPADDING', (0, 0), (0, 0), 12),
    ('LEFTPADDING', (1, 0), (1, 0), 10),
    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ('LINEBELOW', (0, 0), (-1, -1), 2, BLUE),
]))
story.append(ht)
story.append(Spacer(1, 5*mm))

# ── Skills ───────────────────────────────────────────────────────
story.append(Paragraph('专业技能', sec_s))
story.append(HRFlowable(width='100%', thickness=0.8, color=BLUE, spaceAfter=3))
skill_groups = [
    ('编程语言', ['Java（精通）', 'Go（精通）', 'Python（熟悉）']),
    ('数据库',  ['MySQL', 'Redis', 'Elasticsearch', 'ClickHouse', 'MongoDB', 'NebulaGraphDB']),
    ('消息队列', ['Kafka']),
    ('服务器/云', ['Linux', 'Docker', 'Kubernetes', 'Helm', 'S3/Ceph', 'HDFS']),
    ('工具链',   ['Git', 'Jenkins', 'CI/CD', 'gRPC', 'Spring Boot']),
]
rows = [[Paragraph(lbl, sklabel_s), Paragraph('  '.join(tags), tag_s)] for lbl, tags in skill_groups]
st = Table(rows, colWidths=[36*mm, W - 36*mm])
st.setStyle(TableStyle([
    ('ROWBACKGROUNDS', (0, 0), (-1, -1), [LGRAY, WHITE]),
    ('TOPPADDING', (0, 0), (-1, -1), 4),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('LINEBELOW', (0, 0), (-1, -1), 0.3, BORDER),
]))
story.append(st)
story.append(Spacer(1, 4*mm))

# ── Work Experience ───────────────────────────────────────────────
story.append(Paragraph('工作经历', sec_s))
story.append(HRFlowable(width='100%', thickness=0.8, color=BLUE, spaceAfter=3))

jobs = [
    {
        'company': '北京·京东远升科技',
        'role': '软件开发工程师',
        'period': '2025.04 — 至今',
        'bullets': [
            ('领航财务分析系统', '背景：销售团队需实时掌握供应链各环节数据；行动：基于 ClickHouse 设计多维聚合数据模型，采用物化视图+异步预计算；结果：查询响应从 8s 降至 800ms，支持指标配置化组合，灵活度提升 3 倍'),
            ('自定义趋势图看板优化', '背景：原看板 49 个指标各自独立 SQL，维护成本高；行动：抽象为 2 个通用维度聚合 SQL，后端逻辑配置化组合；结果：SQL 从 13 条精简为 2 条，页面加载降低 75%，实现零代码新增指标'),
            ('灭霸看板维度扩展', '背景：业务新增渠道维度需同步修改 10 个指标 SQL；行动：设计维度扩展配置表，改造 SQL 动态字段映射，热插拔上线；结果：新增维度周期从 2 周缩短至 1 天，后续扩展无需改代码'),
        ]
    },
    {
        'company': '深圳·卓驭科技（大疆车载）',
        'role': '中级大数据开发工程师',
        'period': '2024.01 — 2025.04',
        'bullets': [
            ('车载数据闭环平台', '背景：量产业务高速增长，数据资产从千万向亿级演进；行动：主导平台整体架构，搭建 NebulaGraph 图数据库血缘系统，分布式调度引擎 + Kafka 解耦；结果：管理数据资产突破亿条，支撑 10+ 车载业务线，新业务接入周期从 2 周缩至 3 天，SLA 99.9%'),
            ('资产生命周期治理', '背景：无效数据堆积导致存储成本持续增长；行动：建立数据评分体系，实现元信息与存储联动管理，自动化归档清理；结果：每月自动清理无效数据约 200GB，存储成本下降 30%'),
            ('GPS/视频解析工具', '背景：云下云上存储视频需人工降帧率处理；行动：开发流水线自动解析工具，支持 GPS 轨迹和视频预览降帧；结果：单次处理从 4 小时缩短至 20 分钟'),
        ]
    },
    {
        'company': '北京·商汤科技',
        'role': '后端开发工程师',
        'period': '2021.01 — 2024.01',
        'bullets': [
            ('AI 云开发机', '背景：AI 开发者受限于本地算力；行动：设计云原生开发环境后端，K8s+Docker 容器化算力调度，支持 1 卡到多卡弹性伸缩；结果：服务日活开发者 2000+，平均任务排队时间 < 30s'),
            ('广汽感知闭环平台', '背景：感知结果评测依赖人工，成为数据闭环瓶颈；行动：设计异步任务队列 Worker 系统，mpirun+K8s 多卡量化调度，自动标注模块；结果：评测自动化率提升 90%，单次评测周期从 4 小时缩至 30 分钟'),
            ('数据集版本管理平台', '背景：算法团队管理数十个版本数据集，检索效率低下；行动：基于 Elasticsearch 构建元信息+以图搜图引擎，设计索引版本控制与平滑升级；结果：检索 < 100ms，支撑日均 10 万+ 请求'),
            ('HDFS 上云 Ceph（实习）', '背景：HDFS 存储成本高，需迁移至 Ceph；行动：编写 Spark 脚本批量迁移 Avro 数据，针对 5TB 大文件设计 Aws 分片断点续传方案；结果：成功迁移 1PB 数据，成功率 99.99%，节省存储成本 40%'),
        ]
    },
]

for i, job in enumerate(jobs):
    bg = LGRAY if i % 2 == 0 else WHITE
    jt = Table([[
        Paragraph('▸', S('dot', fontName='Hei', fontSize=10, textColor=BLUE, alignment=1, leading=14)),
        [Paragraph(job['company'], company_s),
         Paragraph(job['role'], role_s),
         Paragraph(job['period'], period_s)],
    ]], colWidths=[8*mm, W - 8*mm])
    jt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (0, 0), 6),
        ('LEFTPADDING', (1, 0), (1, 0), 4),
    ]))
    story.append(jt)
    for title, star in job['bullets']:
        story.append(Paragraph(f'<b>{title}</b>', bullet_s))
        # Parse star parts: 背景/行动/结果
        parts = star.split('；')
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Label: bold, value: normal
            label_end = part.find('：')
            if label_end == -1:
                label_end = part.find(':')
            if label_end > 0:
                label = part[:label_end]
                value = part[label_end+1:]
                story.append(Paragraph(f'  <b><font color="#2563eb">{label}</font></b> {value}', star_txt))
            else:
                story.append(Paragraph(f'  {part}', star_txt))
    story.append(Spacer(1, 4*mm))

# ── Education ───────────────────────────────────────────────────
story.append(Paragraph('教育背景', sec_s))
story.append(HRFlowable(width='100%', thickness=0.8, color=BLUE, spaceAfter=3))
et = Table([[
    Paragraph('太原理工大学', school_s),
    Paragraph('2017.09 — 2021.07', S('date', fontName='Hei', fontSize=9, textColor=GRAY, alignment=2, leading=13)),
]], colWidths=[W - 40*mm, 40*mm])
et.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, -1), LGRAY),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('LEFTPADDING', (0, 0), (0, 0), 8),
    ('RIGHTPADDING', (1, 0), (1, 0), 8),
    ('LINEBELOW', (0, 0), (-1, -1), 0.5, BORDER),
]))
story.append(et)
story.append(Paragraph('软件工程 · 本科', major_s))
story.append(Spacer(1, 4*mm))

# ── Honor ──────────────────────────────────────────────────────
story.append(Paragraph('荣誉奖项', sec_s))
story.append(HRFlowable(width='100%', thickness=0.8, color=BLUE, spaceAfter=3))
story.append(Paragraph('★  2019 年全国大学生数学建模竞赛省赛二等奖', honor_s))

# ── Build ───────────────────────────────────────────────────────
doc.build(story)
print(f'PDF生成成功: {output}')
