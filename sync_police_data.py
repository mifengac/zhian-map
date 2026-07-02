#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""云浮市公安局警情可视化平台 - 警情数据库同步工具

主要职责:
1. 连接 Kingbase V8 人民金仓数据库，查询 'ywdata.zq_kshddpt_dsjfx_jq' (警情表) 和 'ywdata.case_type_config' (警情分类配置表)。
2. 将警情数据拉取后，调用 skills 文件夹中的 clean_replies.py 清洗算法，对 'replies' (处警情况) 原文进行清洗。
3. 整合清洗后的字段，输出为 React 前端可以直接读取的 src/assets/incidents.json 和 src/assets/case_type_config.json。
4. 在无数据库连接环境（或环境变量未设置时），自动生成高质量的模拟数据以便开发调试。
"""

import os
import sys
import json
import random
from datetime import datetime, timedelta

# 添加 skills 目录到 path 以便导入清洗模块
sys.path.append(os.path.join(os.path.dirname(__file__), "skills", "dsjjqfx-interface", "scripts"))

try:
    from clean_replies import clean_one
except ImportError:
    # 备用简易清洗函数以防软链接未完全解析
    def clean_one(raw):
        if not raw:
            return {"cjqk_cleaned": "无有效信息", "feedback_source": "无", "disposition_result": "", "data_quality_flag": "无有效信息"}
        # 简单清洗逻辑，过滤中括号时间流水
        cleaned = raw
        import re
        cleaned = re.sub(r'\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}.*?\]', '', cleaned)
        cleaned = cleaned.replace("【结警反馈】", "").replace("【过程反馈】", "").strip()
        return {
            "cjqk_cleaned": cleaned[:120] + "..." if len(cleaned) > 120 else cleaned,
            "feedback_source": "自动清洗",
            "disposition_result": "已现场处理完毕",
            "data_quality_flag": "有效案情"
        }

# ==========================================
# 1. 模拟数据生成器 (无数据库连接时自动降级使用)
# ==========================================
MOCK_CASE_TYPE_CONFIG = [
    {
        "leixing": "打架斗殴",
        "newcharasubclass_list": ["02010899", "02010803", "02010802", "02010801", "02010800"],
        "ay_pattern": "%(殴打|打架|滋事|故意伤害|斗殴)%"
    },
    {
        "leixing": "涉黄",
        "newcharasubclass_list": ["09020100", "09020000", "02051899", "02051801"],
        "ay_pattern": "%(淫|嫖|陪侍|组织未成年人|传播性病)%"
    },
    {
        "leixing": "赌博",
        "newcharasubclass_list": ["09019900", "09010600", "09010500", "02052000"],
        "ay_pattern": "%(赌)%"
    },
    {
        "leixing": "盗窃",
        "newcharasubclass_list": ["02040517", "02040512", "01040300", "01040302"],
        "ay_pattern": "%盗%"
    },
    {
        "leixing": "诈骗",
        "newcharasubclass_list": ["01040402", "01040401", "02040700", "02040600"],
        "ay_pattern": "%(诈|卡)%"
    }
]

DISTRICTS = [
    {"cmdid": "445302", "cmdname": "云城区"},
    {"cmdid": "445303", "cmdname": "云安区"},
    {"cmdid": "445321", "cmdname": "新兴县"},
    {"cmdid": "445322", "cmdname": "郁南县"},
    {"cmdid": "445381", "cmdname": "罗定市"}
]

POLICE_STATIONS = {
    "445302": [
        {"dutydeptna": "44530201", "dutydeptname": "云城派出所", "lat": 22.9298, "lng": 112.0444},
        {"dutydeptna": "44530202", "dutydeptname": "天马派出所", "lat": 22.9350, "lng": 112.0520},
        {"dutydeptna": "44530203", "dutydeptname": "河口派出所", "lat": 22.9410, "lng": 112.0280}
    ],
    "445303": [
        {"dutydeptna": "44530301", "dutydeptname": "六都派出所", "lat": 23.0093, "lng": 111.9515},
        {"dutydeptna": "44530302", "dutydeptname": "白石派出所", "lat": 22.9710, "lng": 111.8920}
    ],
    "445321": [
        {"dutydeptna": "44532101", "dutydeptname": "新城派出所", "lat": 22.6974, "lng": 112.2307},
        {"dutydeptna": "44532102", "dutydeptname": "集成派出所", "lat": 22.6710, "lng": 112.2150}
    ],
    "445322": [
        {"dutydeptna": "44532201", "dutydeptname": "都城派出所", "lat": 23.2303, "lng": 111.5332},
        {"dutydeptna": "44532202", "dutydeptname": "建城派出所", "lat": 23.2080, "lng": 111.5450}
    ],
    "445381": [
        {"dutydeptna": "44538101", "dutydeptname": "罗城派出所", "lat": 22.7688, "lng": 111.5696},
        {"dutydeptna": "44538102", "dutydeptname": "附城派出所", "lat": 22.7810, "lng": 111.5830},
        {"dutydeptna": "44538103", "dutydeptname": "双东派出所", "lat": 22.7560, "lng": 111.6010}
    ]
}

CASE_CONTENTS_MOCK = {
    "打架斗殴": [
        ("报案人称在金山小区门口有两位业主因车位问题发生口角，后引发肢体冲突，双方各持棍棒在推搡，有人员轻微擦伤。", 
         "[2026-07-02 09:12:05] 接警中心派警至河口派出所。[2026-07-02 09:15:30] 民警到达现场。【过程反馈】出警处置情况说明：现场为车位口角，民警已将双方隔开，目前双方情绪稳定，已带回派出所进行调解。处理结果：现场调解。"),
        ("报警人称在酒吧街KTV门口，有多名醉酒年轻人在拉扯打架，现场一片混乱，已有人倒地受伤。",
         "[2026-07-02 01:22:10] 派警。民警赶赴现场。【结警反馈】确认性质：打架斗殴。处理结果说明：民警到场时打架人员已散去，现场将一名受伤醉酒男子送医治疗，现已锁定另外3名嫌疑人，案件正在进一步调查中。处理结果：立案侦查。")
    ],
    "涉黄": [
        ("群众匿名举报称，在某某路养生馆内存在提供色情嫖娼服务的违法行为，有多名陌生男女出入。",
         "[2026-07-02 22:45:00] 云城派出所民警带队突击检查。【结警反馈】处理结果说明：民警当场在养生馆203房间抓获涉嫌卖淫嫖娼的违法人员张某、李某，并对养生馆老板进行传唤。现已对违法人员做出行政拘留处罚。处理结果：行政拘留。")
    ],
    "赌博": [
        ("居民反映在居民楼一楼小卖部后门房间内，每日有人聚众打麻将和使用扑克牌进行大额赌博，噪声扰民严重。",
         "[2026-07-02 16:30:12] 派警。【结警反馈】处理结果说明：民警当场查获参与扑克牌赌博人员6人，收缴赌资5800元，扑克牌2副。目前已对组织者处以行政拘留，参与者处以罚款。处理结果：行政拘留并处罚款。")
    ],
    "盗窃": [
        ("报警人称停在菜市场侧门的一辆红色二轮摩托车被盗，车钥匙当时未拔，买完菜出来发现车已不见。",
         "[2026-07-02 08:20:00] 罗防中队接报。【结警反馈】处理结果说明：民警通过调取菜市场出入口视频监控，发现一名黑衣男子将车骑走。目前已锁定嫌疑人轨迹，正在全力实施抓捕。处理结果：立案研判。")
    ],
    "诈骗": [
        ("报警人称收到一条虚假冒充领导要求转账的微信消息，其信以为真，向对方指定账户转账了50000元，后发现被骗。",
         "[2026-07-02 10:15:20] 反诈中心接报。【结警反馈】处理结果说明：民警接警后立即启动紧急止付程序，对嫌疑人一级卡、二级卡进行快速冻结，成功拦截涉案资金32000元。现已立为刑事案件侦查。处理结果：紧急止付立案。")
    ]
}

def generate_mock_incidents():
    incidents = []
    base_time = datetime.now() - timedelta(days=1)
    
    # 模拟 60 条警情
    for i in range(1, 61):
        dist = random.choice(DISTRICTS)
        station = random.choice(POLICE_STATIONS[dist["cmdid"]])
        
        # 决定警情类型
        cfg = random.choice(MOCK_CASE_TYPE_CONFIG)
        leixing = cfg["leixing"]
        
        # 警情编码映射
        subclass_code = random.choice(cfg["newcharasubclass_list"])
        ori_subclass_code = random.choice(cfg["newcharasubclass_list"])
        
        # 生成时间（均匀分布在 24 小时内）
        incident_time = base_time.replace(hour=random.randint(0, 23), minute=random.randint(0, 59), second=random.randint(0, 59))
        calltime_str = incident_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 获取警情内容和反馈
        content_template = random.choice(CASE_CONTENTS_MOCK[leixing])
        casecontents = content_template[0]
        replies = content_template[1]
        
        # 加上一点抖动，使得警情分布在派出所附近
        lat = station["lat"] + random.uniform(-0.02, 0.02)
        lng = station["lng"] + random.uniform(-0.02, 0.02)
        
        # 调用清洗算法
        cleaned = clean_one(replies)
        
        incident = {
            "caseno": f"JQ-{100000 + i}",
            "calltime": calltime_str,
            "longitude": lng,
            "latitude": lat,
            "neworicharasubclass": ori_subclass_code,
            "newcharasubclass": subclass_code,
            "cmdid": dist["cmdid"],
            "cmdname": dist["cmdname"],
            "dutydeptna": station["dutydeptna"],
            "dutydeptname": station["dutydeptname"],
            "casecontents": casecontents,
            "replies": replies
        }
        # 合并清洗后的字段
        incident.update(cleaned)
        incidents.append(incident)
        
    return incidents

# ==========================================
# 2. 真实数据库连接与抓取
# ==========================================
def sync_from_database():
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        print("⚠️ 未安装 psycopg2 驱动，无法连接 Kingbase 数据库！自动降级为生成模拟数据模式。")
        return None, None

    # 从环境变量读取连接配置
    host = os.getenv("KINGBASE_HOST")
    port = os.getenv("KINGBASE_PORT", "54321")
    dbname = os.getenv("KINGBASE_DBNAME")
    user = os.getenv("KINGBASE_USER")
    password = os.getenv("KINGBASE_PASSWORD")

    if not host or not dbname or not user or not password:
        print("⚠️ 环境变量 KINGBASE_HOST/DBNAME/USER/PASSWORD 未完全设置！自动降级为生成模拟数据模式。")
        return None, None

    print(f"🔌 正在尝试连接数据库 {host}:{port}/{dbname} ...")
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password
        )
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}。自动降级为生成模拟数据模式。")
        return None, None

    try:
        # A. 查询警情分类配置表
        print("📥 正在读取 ywdata.case_type_config ...")
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT leixing, newcharasubclass_list, ay_pattern FROM ywdata.case_type_config")
            config_rows = cur.fetchall()
            configs = [dict(r) for r in config_rows]

        # B. 查询警情数据
        print("📥 正在读取 ywdata.zq_kshddpt_dsjfx_jq ...")
        # 限制只读取最近 1 个月的有空间坐标的警情，防止大屏加载过慢
        sql = """
            SELECT 
                caseno,
                calltime,
                longitude,
                latitude,
                neworicharasubclass,
                newcharasubclass,
                cmdid,
                cmdname,
                dutydeptna,
                dutydeptname,
                casecontents,
                replies
            FROM ywdata.zq_kshddpt_dsjfx_jq
            WHERE longitude IS NOT NULL 
              AND latitude IS NOT NULL
              AND calltime >= (now() - interval '30 day')
            ORDER BY calltime DESC
            LIMIT 1000
        """
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            incident_rows = cur.fetchall()
            print(f"   已抓取到 {len(incident_rows)} 条最新警情数据")

            incidents = []
            for r in incident_rows:
                row_dict = dict(r)
                # 清洗处警情况
                cleaned = clean_one(row_dict.get("replies", ""))
                row_dict.update(cleaned)
                
                # 转换 Decimal 坐标为 Float 以免 JSON 序列化失败
                if row_dict["longitude"] is not None:
                    row_dict["longitude"] = float(row_dict["longitude"])
                if row_dict["latitude"] is not None:
                    row_dict["latitude"] = float(row_dict["latitude"])
                
                incidents.append(row_dict)

        return configs, incidents

    except Exception as e:
        print(f"❌ 数据库执行查询发生异常: {e}")
        return None, None
    finally:
        conn.close()

# ==========================================
# 3. 入口与保存逻辑
# ==========================================
def main():
    assets_dir = os.path.join(os.path.dirname(__file__), "src", "assets")
    os.makedirs(assets_dir, exist_ok=True)

    # 尝试连库同步
    configs, incidents = sync_from_database()

    # 降级为生成模拟数据
    if not incidents:
        print("✨ 正在为您生成高质量的离线模拟警情与配置数据...")
        configs = MOCK_CASE_TYPE_CONFIG
        incidents = generate_mock_incidents()

    # 保存配置
    config_path = os.path.join(assets_dir, "case_type_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(configs, f, ensure_ascii=False, indent=2)
    print(f"💾 已保存警情分类配置文件: {config_path}")

    # 保存警情
    incidents_path = os.path.join(assets_dir, "incidents.json")
    with open(incidents_path, "w", encoding="utf-8") as f:
        json.dump(incidents, f, ensure_ascii=False, indent=2)
    print(f"💾 已保存警情数据列表文件: {incidents_path}")
    print(f"🚀 同步任务圆满完成！")

if __name__ == "__main__":
    main()
