#!/usr/bin/env python3
"""Generate 李亚飞 Resume PDF using ReportLab (v4 compatible)"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# Register Chinese fonts
pdfmetrics.registerFont(TTFont('Hei', '/System/Library/Fonts/STHeiti Medium.ttc'))
pdfmetrics.registerFont(TTFont('Song', '/System/Library/Fonts/Supplemental/Songti.ttc'))

# Color palette
PURPLE = HexColor('#7c3aed')
PURPLE_LIGHT = HexColor('#a78bfa')
DARK_CARD = HexColor('#12121a')
GRAY_TEXT = HexColor('#9ca3af')
LIGHT_TEXT = HexColor('#e2e8f0')
CARD_BG = HexColor('#0f0f15')
CARD_BG2 = HexColor('#13131c')

PAGE_W, PAGE_H = A4
M = 18 * mm

def S(name, **kw):
    base = dict(fontName='Hei', leading=12)
    base.update(kw)
    return ParagraphStyle(name, **base)

title_s   = S('title',   fontName='Hei', fontSize=22, textColor=LIGHT_TEXT, spaceAfter=2, leading=26)
sub_s     = S('sub',     fontName='Hei', fontSize=10, textColor=PURPLE_LIGHT, spaceAfter=4)
meta_s    = S('meta',    fontName='Hei', fontSize=8,  textColor=GRAY_TEXT, spaceAfter=2)
sec_s     = S('sec',     fontName='Hei', fontSize=11, textColor=PURPLE, spaceBefore=8, spaceAfter=4, leading=14)
company_s = S('company',  fontName='Hei', fontSize=10, textColor=LIGHT_TEXT, spaceAfter=1, leading=13)
role_s    = S('role',    fontName='Hei', fontSize=9,  textColor=PURPLE_LIGHT, spaceAfter=1, leading=12)
period_s  = S('period',  fontName='Hei', fontSize=8,  textColor=HexColor('#6b7280'), spaceAfter=3, leading=11)
bullet_s  = S('bullet',   fontName='Hei', fontSize=8,  textColor=GRAY_TEXT, spaceAfter=2, leading=11, leftIndent=8, firstLineIndent=-8)
tag_s     = S('tag',     fontName='Hei', fontSize=8,  textColor=PURPLE_LIGHT, leading=11)
sklabel_s = S('sklabel', fontName='Hei', fontSize=8,  textColor=PURPLE, spaceAfter=2, leading=11)
school_s  = S('school',  fontName='Hei', fontSize=10, textColor=LIGHT_TEXT, spaceAfter=1)
major_s   = S('major',   fontName='Hei', fontSize=9,  textColor=GRAY_TEXT, spaceAfter=1)
honor_s   = S('honor',   fontName='Hei', fontSize=9,  textColor=HexColor('#f9a8d4'), spaceAfter=2, leading=12)
avatar_s  = S('avatar',  fontName='Hei', fontSize=36, textColor=white, alignment=TA_CENTER, leading=42)
dot_s     = S('dot',     fontName='Hei', fontSize=12, textColor=PURPLE, leading=14, alignment=TA_CENTER)

W = PAGE_W - 2 * M  # content width

output = os.path.join(os.path.dirname(__file__), '..', 'static', 'about', 'resume.pdf')
output = os.path.abspath(output)

doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=M, rightMargin=M,
                        topMargin=M, bottomMargin=M)

story = []

# ── Header ───────────────────────────────────────────────────
header_data = [[
    Paragraph('李', avatar_s),
    [Paragraph('李亚飞', title_s),
     Paragraph('四年经验 · 后端开发工程师', sub_s),
     Paragraph('北京  |  17603444963  |  liyafei.work@foxmail.com  |  github.com/RaphaelL2e', meta_s)]
]]
ht = Table(header_data, colWidths=[22*mm, W - 22*mm])
ht.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), DARK_CARD),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('ALIGN', (0,0), (0,0), 'CENTER'),
    ('TOPPADDING', (0,0), (-1,-1), 10),
    ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ('LEFTPADDING', (0,0), (0,0), 8),
    ('LEFTPADDING', (1,0), (1,0), 12),
    ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ('ROUNDEDCORNERS', [6]),
]))
story.append(ht)
story.append(Spacer(1, 6*mm))

# ── Skills ───────────────────────────────────────────────────
story.append(Paragraph('专业技能', sec_s))
story.append(HRFlowable(width='100%', thickness=0.5, color=PURPLE, spaceAfter=4))

skill_groups = [
    ('编程语言', ['Java', 'Go', 'Python']),
    ('数据库',   ['MySQL', 'Redis', 'Elasticsearch', 'ClickHouse', 'MongoDB', 'NebulaGraphDB']),
    ('中间件/框架', ['Kafka', 'gRPC', 'Spring Boot']),
    ('DevOps',   ['Docker', 'Kubernetes', 'Helm', 'Jenkins', 'CI/CD']),
    ('存储/云',  ['S3/Ceph', 'HDFS', 'Linux', 'Git']),
]
rows = [[Paragraph(lbl, sklabel_s), Paragraph('  '.join(tags), tag_s)] for lbl, tags in skill_groups]
st = Table(rows, colWidths=[38*mm, W - 38*mm])
st.setStyle(TableStyle([
    ('ROWBACKGROUNDS', (0,0), (-1,-1), [CARD_BG, CARD_BG2]),
    ('TOPPADDING', (0,0), (-1,-1), 4),
    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ('LEFTPADDING', (0,0), (-1,-1), 8),
    ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('GRID', (0,0), (-1,-1), 0.3, HexColor('#1a1a25')),
]))
story.append(st)
story.append(Spacer(1, 4*mm))

# ── Work Experience ───────────────────────────────────────────
story.append(Paragraph('工作经历', sec_s))
story.append(HRFlowable(width='100%', thickness=0.5, color=PURPLE, spaceAfter=4))

jobs = [
    dict(company='北京 · 京东远升科技', role='软件开发工程师',
         period='2025.04 — 至今 · 北京',
         bullets=[
             '领航财务分析系统：基于 ClickHouse 构建销售供应链分析看板，为业务人员提供直观数据分析支撑',
             '自定义趋势图优化：将 49 个指标 + 13 条 SQL 精简合并为 2 条 SQL，实现配置化多维分析',
             '灭霸看板优化：新增业务维度，调整 10 个指标及对应 SQL 逻辑，提升看板分析维度与准确性',
         ]),
    dict(company='深圳 · 卓驭科技（大疆车载）', role='中级大数据开发工程师',
         period='2024.01 — 2025.04 · 深圳',
         bullets=[
             '车载数据闭环平台：主导资产生命周期治理、血缘建设、亿级数据资产升级（千万→亿级）',
             'NebulaGraph 图数据库：搭建车载资产血缘关系建模与可视化检索',
             '分布式调度引擎 + Kafka 消息队列：实现跨业务系统的任务编排与解耦',
             'GPS 解析 & 视频预览解析工具：流水线自动化，提升数据处理效率',
         ]),
    dict(company='北京 · 商汤科技', role='后端开发工程师',
         period='2021.01 — 2024.01 · 北京',
         bullets=[
             'AI 云开发机：云原生开发环境，支持挂载存储、调用算力池，为 AI 开发者提供端到端开发服务',
             '广汽感知闭环平台：异步任务队列系统、mpirun + K8s 多卡量化任务调度、自动标注系统',
             '数据集版本管理平台：ES 全文检索、以图搜图、数据仓库 ETL 工具开发',
             '数据采标管理平台：数据检索 MVP、分布式数据同步、SDK-Server 模块',
             'HDFS 上云 Ceph（实习）：主导 1PB 数据迁移，Aws 分片方案支持单文件最大 5TB',
         ]),
]

for job in jobs:
    jt = Table([[Paragraph('▸', dot_s),
                 [Paragraph(job['company'], company_s),
                  Paragraph(job['role'], role_s),
                  Paragraph(job['period'], period_s)]]],
               colWidths=[8*mm, W - 8*mm])
    jt.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (0,0), 0),
        ('LEFTPADDING', (1,0), (1,0), 4),
    ]))
    story.append(jt)
    for b in job['bullets']:
        story.append(Paragraph(f'• {b}', bullet_s))
    story.append(Spacer(1, 4*mm))

# ── Education ─────────────────────────────────────────────────
story.append(Paragraph('教育背景', sec_s))
story.append(HRFlowable(width='100%', thickness=0.5, color=PURPLE, spaceAfter=4))

et = Table([[Paragraph('太原理工大学', school_s),
             Paragraph('2017.09 — 2021.07',
                       S('date', fontName='Hei', fontSize=9, textColor=HexColor('#6b7280'),
                         alignment=TA_CENTER, leading=13))]],
           colWidths=[W - 40*mm, 40*mm])
et.setStyle(TableStyle([
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('BACKGROUND', (0,0), (-1,-1), CARD_BG),
    ('TOPPADDING', (0,0), (-1,-1), 6),
    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ('LEFTPADDING', (0,0), (0,0), 8),
    ('RIGHTPADDING', (1,0), (1,0), 8),
    ('LINEBELOW', (0,0), (-1,-1), 0.3, HexColor('#1a1a25')),
]))
story.append(et)
story.append(Paragraph('软件工程 · 本科', major_s))
story.append(Spacer(1, 4*mm))

# ── Honor ────────────────────────────────────────────────────
story.append(Paragraph('荣誉奖项', sec_s))
story.append(HRFlowable(width='100%', thickness=0.5, color=PURPLE, spaceAfter=4))
story.append(Paragraph('★ 2019年全国数学建模省赛二等奖', honor_s))

# ── Build ────────────────────────────────────────────────────
doc.build(story)
print(f'PDF生成成功: {output}')
