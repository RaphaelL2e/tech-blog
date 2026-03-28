#!/usr/bin/env python3
"""Generate 李亚飞 Resume PDF - High Quality Version"""

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
    d = dict(fontName='Hei', leading=12)
    d.update(kw)
    return ParagraphStyle(name, **d)

title_s   = S('title',   fontSize=20, textColor=DARK,    spaceAfter=2, leading=24)
sub_s     = S('sub',    fontSize=10, textColor=BLUE,    spaceAfter=2)
meta_s    = S('meta',   fontSize=8.5, textColor=GRAY,   spaceAfter=1)
sec_s     = S('sec',    fontSize=11, textColor=BLUE,     spaceBefore=8, spaceAfter=3, leading=14)
company_s = S('comp',   fontSize=10, textColor=DARK,     spaceAfter=1, leading=13)
role_s    = S('role',   fontSize=9,  textColor=BLUE,    spaceAfter=1, leading=12)
period_s  = S('per',    fontSize=8,  textColor=GRAY,    spaceAfter=3, leading=11)
bullet_s  = S('bul',    fontSize=8.5, textColor=GRAY,   spaceAfter=2, leading=12, leftIndent=14, firstLineIndent=-12)
sklabel_s = S('skl',   fontSize=8,  textColor=GRAY,   leading=11)
tag_s     = S('tag',    fontSize=8,  textColor=DARK,    leading=11)
school_s  = S('sch',    fontSize=10, textColor=DARK,    spaceAfter=1)
major_s   = S('maj',    fontSize=9,  textColor=GRAY,    spaceAfter=1)
honor_s   = S('hon',    fontSize=9,  textColor=DARK,    spaceAfter=2, leading=12)
star_lbl  = S('slbl',  fontSize=8,  textColor=BLUE,   spaceAfter=1, leading=11)
star_txt  = S('stxt',  fontSize=8.5, textColor=GRAY,   spaceAfter=2, leading=12)

W = PAGE_W - 2 * M
out = os.path.join(os.path.dirname(__file__), '..', 'static', 'about', 'resume.pdf')
out = os.path.abspath(out)

doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=M, rightMargin=M, topMargin=M, bottomMargin=M)
story = []

# ── Header ────────────────────────────────────────────────────
av_w = 18 * mm
header_data = [[
    Paragraph('李', S('av', fontSize=26, textColor=WHITE, alignment=1, leading=30)),
    [Paragraph('李亚飞', title_s),
     Paragraph('四年经验 · 后端开发工程师 · 北京', sub_s),
     Paragraph('17603444963  |  liyafei.work@foxmail.com  |  github.com/RaphaelL2e', meta_s)],
]]
ht = Table(header_data, colWidths=[av_w, W - av_w])
ht.setStyle(TableStyle([
    ('BACKGROUND', (0,0),(-1,-1), LGRAY),
    ('VALIGN', (0,0),(-1,-1), 'MIDDLE'),
    ('TOPPADDING',(0,0),(-1,-1), 10),
    ('BOTTOMPADDING',(0,0),(-1,-1), 10),
    ('LEFTPADDING',(0,0),(0,0), 12),
    ('LEFTPADDING',(1,0),(1,0), 10),
    ('RIGHTPADDING',(0,0),(-1,-1), 10),
    ('LINEBELOW',(0,0),(-1,-1), 2, BLUE),
]))
story.append(ht)
story.append(Spacer(1, 5*mm))

# ── Skills ─────────────────────────────────────────────────────
story.append(Paragraph('专业技能', sec_s))
story.append(HRFlowable(width='100%', thickness=0.8, color=BLUE, spaceAfter=3))
skill_groups = [
    ('编程语言', ['Java（精通）', 'Go（精通）', 'Python（熟悉）']),
    ('数据库',   ['MySQL', 'Redis', 'Elasticsearch', 'ClickHouse', 'MongoDB', 'NebulaGraphDB']),
    ('消息队列', ['Kafka']),
    ('服务器/云',['Linux', 'Docker', 'Kubernetes', 'Helm', 'S3/Ceph', 'HDFS']),
    ('工具链',   ['Git', 'Jenkins', 'CI/CD', 'gRPC', 'Spring Boot']),
]
rows = [[Paragraph(lbl, sklabel_s), Paragraph('  '.join(tags), tag_s)] for lbl, tags in skill_groups]
st = Table(rows, colWidths=[36*mm, W-36*mm])
st.setStyle(TableStyle([
    ('ROWBACKGROUNDS',(0,0),(-1,-1),[LGRAY,WHITE]),
    ('TOPPADDING',(0,0),(-1,-1), 4),
    ('BOTTOMPADDING',(0,0),(-1,-1), 4),
    ('LEFTPADDING',(0,0),(-1,-1), 8),
    ('RIGHTPADDING',(0,0),(-1,-1), 8),
    ('VALIGN',(0,0),(-1,-1), 'MIDDLE'),
    ('LINEBELOW',(0,0),(-1,-1), 0.3, BORDER),
]))
story.append(st)
story.append(Spacer(1, 4*mm))

# ── Work Experience ─────────────────────────────────────────────
story.append(Paragraph('工作经历', sec_s))
story.append(HRFlowable(width='100%', thickness=0.8, color=BLUE, spaceAfter=3))

# Each job: (company, role, period, [(project_title, star_text)])
jobs = [

    # ── 京东 ──
    ('北京·京东远升科技', '软件开发工程师', '2025.04 — 至今',
     [
         ('领航财务分析看板',
          '基于 ClickHouse 构建多维聚合数据模型，引入物化视图+异步预计算策略，将查询'
          'RT 从 8s 压缩至 800ms；设计指标配置化引擎，业务可自主组合指标维度，'
          '无需研发介入即可新增看板，将看板搭建周期从 5 天缩短至 2 小时'),

         ('趋势图看板性能重构',
          '针对 13 条独立 SQL 导致页面加载慢、维护成本高的问题，'
          '将指标按维度归类合并为 2 条通用聚合 SQL，通过后端逻辑驱动配置化组合；'
          'SQL 数量减少 85%，前端首屏加载降低 75%，后续新增指标零代码改动'),

         ('灭霸看板维度扩展',
          '设计维度扩展配置表 + 动态字段映射机制，支持新渠道维度热插拔上线；'
          '改造 10 个核心指标及关联取数逻辑，新维度上线周期从 2 周压缩至 1 天，'
          '彻底消除后续扩展中的代码改动'),
     ]),

    # ── 大疆车载 ──
    ('深圳·卓驭科技（大疆车载）', '中级大数据开发工程师', '2024.01 — 2025.04',
     [
         ('车载数据闭环平台 · 整体架构',
          '主导亿级数据资产平台从架构设计到落地全流程，引入 NebulaGraph 图数据库建模资产血缘，'
          '设计分布式调度引擎（抽象工厂模式）支撑任务快速编排；'
          '基于 Kafka 实现跨业务系统回调解耦；'
          '平台管理资产突破亿条，支撑 10+ 车载业务线，新业务接入从 2 周缩至 3 天，日调度 50 万+ 任务，SLA 99.9%'),

         ('资产生命周期治理体系',
          '建立数据质量评分体系，打通元信息与物理存储的联动管理链路，'
          '实现无效数据的自动化识别、归档与清理；'
          '每月清理无效数据约 200GB，整体存储成本下降 30%，数据资产健康度可视化'),

         ('GPS/视频解析工具链',
          '设计并实现流水线自动解析框架，支持云上云下视频降帧率处理与 GPS 轨迹自动化抽取；'
          '单次视频处理耗时从 4 小时缩短至 20 分钟，准确率 99%+，支撑数据闭环高效运转'),
     ]),

    # ── 商汤 ──
    ('北京·商汤科技', '后端开发工程师', '2021.01 — 2024.01',
     [
         ('AI 云开发机平台',
          '设计云原生开发环境后端，基于 K8s+Docker 实现算力池弹性调度，支持 1 卡到多卡无缝伸缩；'
          '提供存储挂载、代码调试、模型训练全流程覆盖；'
          '服务日活开发者 2000+，平均任务排队时间 < 30s，稳定性 SLA 99.9%'),

         ('广汽感知闭环平台',
          '设计异步任务队列系统，Worker 服务专门执行评测任务，支持评测算法热插拔；'
          '基于 mpirun + K8s API 实现多卡量化任务调度，精确收集量化结果供下游使用；'
          '构建自动标注模块，实现感知轨迹的预测和标注；'
          '评测自动化率提升 90%，单次评测周期从 4 小时缩短至 30 分钟'),

         ('数据集版本管理平台',
          '基于 Elasticsearch 构建元信息全文检索系统，支持多维度过滤与聚合；'
          '开发以图搜图引擎，实现图片数据的视觉特征检索；'
          '设计索引版本控制与平滑升级机制保障高可用；'
          '检索 P99 < 100ms，支撑日均 10 万+ 检索请求，算法团队数据查找效率提升 5 倍'),

         ('HDFS 上云 Ceph（实习）',
          '主导 1PB 数据从 HDFS 向 Ceph 对象存储的迁移工程，'
          '编写 Spark 脚本批量处理 Avro 格式数据，针对 5TB 级大文件设计 Aws 分片断点续传；'
          '迁移成功率 99.99%，零数据丢失，直接节省存储成本约 40%'),
     ]),
]

for i, (company, role, period, projects) in enumerate(jobs):
    bg = LGRAY if i % 2 == 0 else WHITE
    jt = Table([[
        Paragraph('▸', S('dot', fontSize=10, textColor=BLUE, alignment=1, leading=14)),
        [Paragraph(company, company_s),
         Paragraph(role, role_s),
         Paragraph(period, period_s)],
    ]], colWidths=[8*mm, W-8*mm])
    jt.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1), bg),
        ('VALIGN',(0,0),(-1,-1), 'TOP'),
        ('TOPPADDING',(0,0),(-1,-1), 4),
        ('BOTTOMPADDING',(0,0),(-1,-1), 2),
        ('LEFTPADDING',(0,0),(0,0), 6),
        ('LEFTPADDING',(1,0),(1,0), 4),
    ]))
    story.append(jt)
    for proj_title, star in projects:
        story.append(Paragraph(f'<b>{proj_title}</b>', bullet_s))
        # Wrap long text nicely
        story.append(Paragraph(star, star_txt))
    story.append(Spacer(1, 4*mm))

# ── Education ─────────────────────────────────────────────────
story.append(Paragraph('教育背景', sec_s))
story.append(HRFlowable(width='100%', thickness=0.8, color=BLUE, spaceAfter=3))
et = Table([[
    Paragraph('太原理工大学', school_s),
    Paragraph('2017.09 — 2021.07', S('date', fontSize=9, textColor=GRAY, alignment=2, leading=13)),
]], colWidths=[W-40*mm, 40*mm])
et.setStyle(TableStyle([
    ('BACKGROUND',(0,0),(-1,-1), LGRAY),
    ('VALIGN',(0,0),(-1,-1), 'MIDDLE'),
    ('TOPPADDING',(0,0),(-1,-1), 6),
    ('BOTTOMPADDING',(0,0),(-1,-1), 6),
    ('LEFTPADDING',(0,0),(0,0), 8),
    ('RIGHTPADDING',(1,0),(1,0), 8),
    ('LINEBELOW',(0,0),(-1,-1), 0.5, BORDER),
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
print(f'PDF生成成功: {out}')
