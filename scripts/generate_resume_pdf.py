#!/usr/bin/env python3
"""Generate 李亚飞 Resume PDF - Technical Depth Enhanced"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pdfencrypt import StandardEncryption
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

pdfmetrics.registerFont(TTFont('Hei', '/System/Library/Fonts/STHeiti Medium.ttc'))
pdfmetrics.registerFont(TTFont('Song', '/System/Library/Fonts/Supplemental/Songti.ttc'))

BLUE   = HexColor('#2563eb')
DARK   = HexColor('#1a1a2e')
GRAY   = HexColor('#6b7280')
LGRAY  = HexColor('#f3f4f6')
BORDER = HexColor('#d1d5db')
WHITE  = white

PAGE_W, PAGE_H = A4
M = 16 * mm

def S(name, **kw):
    d = dict(fontName='Hei', leading=12)
    d.update(kw)
    return ParagraphStyle(name, **d)

title_s    = S('title',  fontSize=20, textColor=DARK,  spaceAfter=2, leading=24)
sub_s      = S('sub',   fontSize=10, textColor=BLUE,  spaceAfter=2)
meta_s     = S('meta',  fontSize=8.5, textColor=GRAY, spaceAfter=1)
sec_s      = S('sec',   fontSize=11, textColor=BLUE,  spaceBefore=8, spaceAfter=3, leading=14)
overview_s  = S('over',  fontSize=9,  textColor=DARK,  spaceAfter=3, leading=14)
company_s  = S('comp',  fontSize=10, textColor=DARK,  spaceAfter=1, leading=13)
role_s     = S('role',  fontSize=9,  textColor=BLUE,  spaceAfter=1, leading=12)
period_s   = S('per',   fontSize=8,  textColor=GRAY,  spaceAfter=3, leading=11)
bullet_s   = S('bul',   fontSize=8.5, textColor=GRAY, spaceAfter=2, leading=12, leftIndent=14, firstLineIndent=-12)
detail_s   = S('det',   fontSize=8.5, textColor=GRAY, spaceAfter=3, leading=12)
tag_s      = S('tag',   fontSize=7.5, textColor=BLUE,  spaceAfter=1, leading=10)
sklabel_s  = S('skl',   fontSize=8,  textColor=GRAY,  leading=11)
tagval_s   = S('tv',    fontSize=8,  textColor=DARK,  leading=11)
school_s   = S('sch',   fontSize=10, textColor=DARK,  spaceAfter=1)
major_s    = S('maj',   fontSize=9,  textColor=GRAY,  spaceAfter=1)
honor_s    = S('hon',   fontSize=9,  textColor=DARK,  spaceAfter=2, leading=12)
dot_s      = S('dot',   fontSize=10, textColor=BLUE,  alignment=1, leading=14)

W = PAGE_W - 2 * M
out = os.path.join(os.path.dirname(__file__), '..', 'static', 'about', 'resume.pdf')
out = os.path.abspath(out)

encrypt = StandardEncryption('4963')
doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=M, rightMargin=M, topMargin=M, bottomMargin=M, encrypt=encrypt)
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
    ('BACKGROUND',(0,0),(-1,-1),LGRAY),
    ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ('TOPPADDING',(0,0),(-1,-1),10),
    ('BOTTOMPADDING',(0,0),(-1,-1),10),
    ('LEFTPADDING',(0,0),(0,0),12),
    ('LEFTPADDING',(1,0),(1,0),10),
    ('RIGHTPADDING',(0,0),(-1,-1),10),
    ('LINEBELOW',(0,0),(-1,-1),2,BLUE),
]))
story.append(ht)
story.append(Spacer(1, 5*mm))

# ── Technical Overview ──────────────────────────────────────────
story.append(Paragraph('技术亮点', sec_s))
story.append(HRFlowable(width='100%', thickness=0.8, color=BLUE, spaceAfter=3))

overview_items = [
    ('分布式系统', '主导设计并落地亿级数据资产平台，基于 K8s + Docker 容器编排，支持多卡算力弹性伸缩，日调度任务 50 万+，SLA 99.9%'),
    ('大数据工程', '基于 ClickHouse / Elasticsearch / NebulaGraph 构建数据分析引擎，日处理数据量 PB 级；Kafka 消息队列日均吞吐千万条，零消息丢失'),
    ('后端架构', '精通 Java / Go 双语言后端开发，擅长 gRPC 微服务设计；Spring Boot + MySQL + Redis 构建高并发 API，接口 P99 < 100ms'),
]

for icon, text in overview_items:
    row = [[
        Paragraph(f'<b><font color="#2563eb">{icon}</font></b>', S('ol', fontSize=9, textColor=BLUE, leading=13)),
        Paragraph(text, S('ov', fontSize=9, textColor=GRAY, leading=13)),
    ]]
    rt = Table(row, colWidths=[38*mm, W - 38*mm])
    rt.setStyle(TableStyle([
        ('ROWBACKGROUNDS',(0,0),(-1,-1),[LGRAY,WHITE]),
        ('TOPPADDING',(0,0),(-1,-1),4),
        ('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('LEFTPADDING',(0,0),(-1,-1),8),
        ('RIGHTPADDING',(0,0),(-1,-1),8),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LINEBELOW',(0,0),(-1,-1),0.3,BORDER),
    ]))
    story.append(rt)
story.append(Spacer(1, 4*mm))

# ── Technical Skills ───────────────────────────────────────────
story.append(Paragraph('技术栈', sec_s))
story.append(HRFlowable(width='100%', thickness=0.8, color=BLUE, spaceAfter=3))

skill_groups = [
    ('编程语言', ['Java（精通）', 'Go（精通）', 'Python（熟悉）']),
    ('大数据',   ['ClickHouse', 'Elasticsearch', 'Kafka', 'NebulaGraphDB', 'Flink', 'MongoDB']),
    ('关系型/缓存', ['MySQL', 'Redis']),
    ('DevOps',  ['Docker', 'Kubernetes', 'Helm', 'Jenkins', 'CI/CD']),
    ('云/存储',  ['S3/Ceph', 'HDFS', 'Linux', 'Git']),
    ('框架/协议', ['Spring Boot', 'gRPC', 'RESTful API']),
]
rows = [[Paragraph(lbl, sklabel_s), Paragraph('  '.join(tags), tagval_s)] for lbl, tags in skill_groups]
st = Table(rows, colWidths=[38*mm, W - 38*mm])
st.setStyle(TableStyle([
    ('ROWBACKGROUNDS',(0,0),(-1,-1),[LGRAY,WHITE]),
    ('TOPPADDING',(0,0),(-1,-1),4),
    ('BOTTOMPADDING',(0,0),(-1,-1),4),
    ('LEFTPADDING',(0,0),(-1,-1),8),
    ('RIGHTPADDING',(0,0),(-1,-1),8),
    ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ('LINEBELOW',(0,0),(-1,-1),0.3,BORDER),
]))
story.append(st)
story.append(Spacer(1, 4*mm))

# ── Work Experience ─────────────────────────────────────────────
story.append(Paragraph('工作经历', sec_s))
story.append(HRFlowable(width='100%', thickness=0.8, color=BLUE, spaceAfter=3))

jobs = [
    ('北京·京东集团', '软件开发工程师 · 即时履约部', '2025.04 — 至今', LGRAY,
     '【技术栈：Java | Spring Boot | ClickHouse | Kafka | Flink | MySQL | Redis | gRPC】',
     [
         ('前置仓实时数据大屏（主导，日处理 50 万 + 订单）',
          '主导前置仓实时数据大屏项目，基于 Flink + Redis 实时流处理架构；'
          '接入订单、物流、库存等多源实时数据流，日处理订单量 50 万 +；'
          '大屏核心指标 30+，秒级延迟，为运营决策提供实时数据支撑'),

         ('前置仓运营平台（排班 + 预测单量 + 仓任务）',
          '负责人员排班管理模块，支持多班次、多人员类型的智能排班配置；'
          '构建预测单量模型管理，集成时序预测算法，实现单量智能预测；'
          '仓任务管理模块，覆盖收货、上架、拣货等全链路任务调度'),

         ('智能排班系统（MQ 跨部门自动化）',
          '利用数据驱动人员排班优化，基于历史单量数据训练排班预测模型；'
          '跨部门接入排班系统 MQ，实现自动化排班触发与消息推送；'
          '排班效率提升 50%，人效优化 20%+'),

         ('领航财务分析看板（点击率↑300%）',
          '基于 ClickHouse 设计多维聚合数据模型，物化视图 + 异步预计算将查询 RT 从 8s 降至 800ms；'
          '设计指标配置化引擎，业务自主组合维度，搭建周期从 5 天缩至 2 小时；'
          '引入 Kafka 异步消息队列，解耦数据生产与消费链路，峰值 TPS 5000+'),
     ]),

    ('深圳·卓驭科技（大疆车载）', '中级大数据开发工程师', '2024.01 — 2025.04', WHITE,
     '【技术栈：Java | Spring Boot | NebulaGraph | Kafka | K8s | Spark】',
     [
         ('车载数据闭环平台 · 整体架构（资产规模：亿级）',
          '主导亿级数据资产平台架构设计与落地，NebulaGraph 图数据库建模资产血缘关系；'
          '设计分布式调度引擎（抽象工厂模式）实现任务快速编排，Kafka 解耦跨业务回调解耦；'
          '平台管理资产突破亿条，支撑 10+ 车载业务线，新业务接入周期从 2 周缩至 3 天，'
          '日调度任务 50 万+，SLA 99.9%'),

         ('资产生命周期治理',
          '建立数据质量评分体系，打通元信息与物理存储联动管理链路；'
          '实现无效数据自动化识别、归档与清理；'
          '每月清理无效数据约 200GB，存储成本下降 30%'),

         ('GPS/视频解析工具',
          '设计流水线自动解析框架，支持云上云下视频降帧率处理与 GPS 轨迹自动化抽取；'
          '单次处理从 4 小时缩短至 20 分钟，准确率 99%+；'
          '处理数据覆盖全国主要城市路网，日处理视频帧数 500 万+'),
     ]),

    ('北京·商汤科技', '后端开发工程师', '2021.01 — 2024.01', LGRAY,
     '【技术栈：Go | Python | K8s | Elasticsearch | HDFS | Ceph | gRPC】',
     [
         ('AI 云开发机平台（用户：2000+ 开发者）',
          '设计云原生开发环境后端，K8s + Docker 容器化算力调度，支持 1 卡到多卡弹性伸缩；'
          '基于 gRPC 构建内部通信协议，接口延迟 < 5ms；'
          '服务日活开发者 2000+，平均任务排队时间 < 30s，可用率 99.9%'),

         ('广汽感知闭环平台',
          '设计异步任务队列系统，Worker 专门执行评测任务，支持评测算法热插拔；'
          '基于 mpirun + K8s API 实现多卡量化任务调度，精确收集量化结果；'
          '构建感知轨迹自动标注模块；'
          '评测自动化率提升 90%，单次评测从 4 小时缩短至 30 分钟'),

         ('数据集版本管理平台（QPS：10000+）',
          '基于 Elasticsearch 构建元信息检索系统，支持多维度过滤与全文搜索；'
          '开发以图搜图引擎，实现图片视觉特征高效检索；'
          '设计索引版本控制与平滑升级机制保障高可用；'
          '检索 P99 < 100ms，支撑日均 10 万+ 请求，算法团队数据查找效率提升 5 倍'),

         ('HDFS 上云 Ceph（实习，1PB 数据迁移）',
          '主导 1PB 数据从 HDFS 向 Ceph 对象存储迁移，编写 Spark 脚本批量处理 Avro 数据；'
          '针对 5TB 级大文件设计 Aws 分片断点续传方案；'
          '迁移成功率 99.99%，零数据丢失，存储成本节省 40%'),
     ]),
]

for company, role, period, bg, tech_tags, projects in jobs:
    jt = Table([[
        Paragraph('▸', dot_s),
        [Paragraph(company, company_s),
         Paragraph(role, role_s),
         Paragraph(period, period_s)],
    ]], colWidths=[8*mm, W-8*mm])
    jt.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),bg),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),4),
        ('BOTTOMPADDING',(0,0),(-1,-1),2),
        ('LEFTPADDING',(0,0),(0,0),6),
        ('LEFTPADDING',(1,0),(1,0),4),
    ]))
    story.append(jt)
    # Tech tags row
    story.append(Paragraph(tech_tags, S('tt', fontSize=7.5, textColor=BLUE, spaceAfter=2, leading=10)))
    for proj_title, detail in projects:
        story.append(Paragraph(f'<b>{proj_title}</b>', bullet_s))
        story.append(Paragraph(detail, detail_s))
    story.append(Spacer(1, 4*mm))

# ── Education ───────────────────────────────────────────────────
story.append(Paragraph('教育背景', sec_s))
story.append(HRFlowable(width='100%', thickness=0.8, color=BLUE, spaceAfter=3))
et = Table([[
    Paragraph('太原理工大学', school_s),
    Paragraph('2017.09 — 2021.07', S('date', fontSize=9, textColor=GRAY, alignment=2, leading=13)),
]], colWidths=[W-40*mm, 40*mm])
et.setStyle(TableStyle([
    ('BACKGROUND',(0,0),(-1,-1),LGRAY),
    ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ('TOPPADDING',(0,0),(-1,-1),6),
    ('BOTTOMPADDING',(0,0),(-1,-1),6),
    ('LEFTPADDING',(0,0),(0,0),8),
    ('RIGHTPADDING',(1,0),(1,0),8),
    ('LINEBELOW',(0,0),(-1,-1),0.5,BORDER),
]))
story.append(et)
story.append(Paragraph('软件工程 · 本科', major_s))
story.append(Spacer(1, 4*mm))

# ── Honor ─────────────────────────────────────────────────────
story.append(Paragraph('荣誉奖项', sec_s))
story.append(HRFlowable(width='100%', thickness=0.8, color=BLUE, spaceAfter=3))
story.append(Paragraph('★  2019 年全国大学生数学建模竞赛省赛二等奖', honor_s))

# ── Build ─────────────────────────────────────────────────────
doc.build(story)
print(f'PDF生成成功: {out}')
