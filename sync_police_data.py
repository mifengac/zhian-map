#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""云浮市公安局警情可视化平台 - 警情数据库同步工具

主要职责:
1. 连接 Kingbase V8 人民金仓数据库，查询 'ywdata.zq_kshddpt_dsjfx_jq' (警情表) 和 'ywdata.case_type_config' (警情分类配置表)。
2. 将警情数据拉取后，调用 skills 中的 clean_replies.py 清洗算法对 'replies' 进行清洗。
3. 整合清洗后的字段，输出为 src/assets/incidents.json 和 src/assets/case_type_config.json。
4. 数据库字段适配：经度使用 `lngofcriterion`，纬度使用 `latofcriterion`。
5. 生成 6 月 1 日至 7 月 5 日的警情测试数据（包含 21:00 - 23:00 之间的打架斗殴警情）。
"""

import os
import sys
import json
import random
from datetime import datetime, timedelta


# ==========================================
# 0. 载入本地 .env 环境变量文件 (零依赖实现)
# ==========================================
def load_env_file(filepath=".env"):
    if not os.path.exists(filepath):
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if not os.path.exists(filepath):
            return
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'").strip('"')
                    os.environ[key] = val
    except Exception as e:
        print(f"⚠️ 读取 .env 配置文件失败: {e}")

load_env_file()

# 添加 skills 目录以导入清洗模块
sys.path.append(os.path.join(os.path.dirname(__file__), "skills", "dsjjqfx-interface", "scripts"))

try:
    from clean_replies import clean_one
except ImportError:
    def clean_one(raw):
        if not raw:
            return {"cjqk_cleaned": "无有效信息", "feedback_source": "无", "disposition_result": "", "data_quality_flag": "无有效信息"}
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
        ("在金山小区门口有两位业主因车位纠纷发生口角，后升级为肢体冲突，双方情绪激动持械打斗，致使一人手臂擦伤出血。", 
         "[2026-06-15 21:12:05] 接警中心派警至河口派出所。[2026-06-15 21:15:30] 民警到达现场。【过程反馈】出警处置情况说明：现场为车位纠纷，民警已将打架双方控制，带回派出所调解。处理结果：带回调查。"),
        ("在酒吧街KTV门口，多名年轻男子因酒后摩擦发生聚众打架，现场拉扯斗殴，有人头部受伤流血。",
         "[2026-06-18 22:30:10] 派警。民警赶赴现场。【结警反馈】确认性质：打架斗殴。处理结果说明：民警到场将双方当事人控制，受伤人员已送医。目前依法对打架主谋执行行政拘留十日。处理结果：行政拘留。")
    ],
    "涉黄": [
        ("群众匿名举报称，在某某养生馆内存在色情交易嫖娼行为，有多名陌生男子深夜出入。",
         "[2026-06-12 23:45:00] 突击检查。【结警反馈】处理结果说明：民警当场在养生馆203房间抓获涉嫌卖淫嫖娼人员2人，已作行政拘留。处理结果：行政拘留。")
    ],
    "赌博": [
        ("居民反映在居民楼小卖部二楼房间内，每日深夜有人聚众大额赌博，噪声扰民严重。",
         "[2026-06-20 16:30:12] 派警。【结警反馈】处理结果说明：民警当场查获参与扑克牌赌博人员6人，收缴赌资5800元。处理结果：罚款处罚。")
    ],
    "盗窃": [
        ("报警人称停在路口的一辆红色二轮摩托车被盗，车钥匙忘拔，买完东西出来发现车已不见。",
         "[2026-06-25 08:20:00] 罗防接报。【结警反馈】处理结果说明：通过监控锁定一名男子，已立案追踪。处理结果：立案研判。")
    ],
    "诈骗": [
        ("报警人称收到冒充单位领导要求转账的短信，其信以为真，向对方指定账户转账了50000元，后发现被骗。",
         "[2026-06-22 10:15:20] 反诈接报。【结警反馈】处理结果说明：民警快速止付冻结嫌疑账户，已挽回部分损失。处理结果：紧急止付。")
    ]
}

def generate_mock_incidents():
    incidents = []
    
    # 模拟数据范围为 2026-06-01 至 2026-07-05 之间
    start_date = datetime(2026, 6, 1)
    end_date = datetime(2026, 7, 5)
    days_range = (end_date - start_date).days

    # 1. 特意生成 6 月份以来每晚 21-23 点的 "打架斗殴" 核心警情
    for i in range(1, 11):
        dist = random.choice(DISTRICTS)
        station = random.choice(POLICE_STATIONS[dist["cmdid"]])
        cfg = MOCK_CASE_TYPE_CONFIG[0] # 打架斗殴
        subclass_code = random.choice(cfg["newcharasubclass_list"])
        ori_subclass_code = random.choice(cfg["newcharasubclass_list"])
        
        # 强制设为 6 月份的 21点 至 23点
        random_day = start_date + timedelta(days=random.randint(0, 29))
        incident_time = random_day.replace(hour=random.randint(21, 22), minute=random.randint(0, 59), second=random.randint(0, 59))
        calltime_str = incident_time.strftime("%Y-%m-%d %H:%M:%S")
        
        content_template = random.choice(CASE_CONTENTS_MOCK["打架斗殴"])
        casecontents = content_template[0]
        replies = content_template[1]
        
        lat = station["lat"] + random.uniform(-0.01, 0.01)
        lng = station["lng"] + random.uniform(-0.01, 0.01)
        cleaned = clean_one(replies)
        
        incident = {
            "caseno": f"JQ-CORE-{1000 + i}",
            "calltime": calltime_str,
            "lngofcriterion": lng,
            "latofcriterion": lat,
            "neworicharasubclass": ori_subclass_code,
            "newcharasubclass": subclass_code,
            "cmdid": dist["cmdid"],
            "cmdname": dist["cmdname"],
            "dutydeptna": station["dutydeptna"],
            "dutydeptname": station["dutydeptname"],
            "casecontents": casecontents,
            "replies": replies
        }
        incident.update(cleaned)
        incidents.append(incident)

    # 2. 随机生成 70 条背景警情数据（分布在 6/1 到 7/5）
    for i in range(1, 71):
        dist = random.choice(DISTRICTS)
        station = random.choice(POLICE_STATIONS[dist["cmdid"]])
        cfg = random.choice(MOCK_CASE_TYPE_CONFIG)
        leixing = cfg["leixing"]
        
        subclass_code = random.choice(cfg["newcharasubclass_list"])
        ori_subclass_code = random.choice(cfg["newcharasubclass_list"])
        
        # 生成 6-7 月之间的时间
        random_day = start_date + timedelta(days=random.randint(0, days_range))
        incident_time = random_day.replace(hour=random.randint(0, 23), minute=random.randint(0, 59), second=random.randint(0, 59))
        calltime_str = incident_time.strftime("%Y-%m-%d %H:%M:%S")
        
        content_template = random.choice(CASE_CONTENTS_MOCK[leixing])
        casecontents = content_template[0]
        replies = content_template[1]
        
        lat = station["lat"] + random.uniform(-0.02, 0.02)
        lng = station["lng"] + random.uniform(-0.02, 0.02)
        cleaned = clean_one(replies)
        
        incident = {
            "caseno": f"JQ-BG-{2000 + i}",
            "calltime": calltime_str,
            "lngofcriterion": lng,
            "latofcriterion": lat,
            "neworicharasubclass": ori_subclass_code,
            "newcharasubclass": subclass_code,
            "cmdid": dist["cmdid"],
            "cmdname": dist["cmdname"],
            "dutydeptna": station["dutydeptna"],
            "dutydeptname": station["dutydeptname"],
            "casecontents": casecontents,
            "replies": replies
        }
        incident.update(cleaned)
        incidents.append(incident)
        
    return incidents

# ==========================================
# 2. 真实数据库连接与抓取 (适配新字段名 lngofcriterion/latofcriterion)
# ==========================================
def sync_from_database():
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        print("⚠️ 未安装 psycopg2 驱动，无法连接 Kingbase 数据库！自动降级为生成模拟数据模式。")
        return None, None

    host = os.getenv("KINGBASE_HOST") or os.getenv("DB_HOST", "192.168.1.137")
    port = os.getenv("KINGBASE_PORT") or os.getenv("DB_PORT", "54321")
    dbname = os.getenv("KINGBASE_DBNAME") or os.getenv("DB_NAME", "yfywk")
    user = os.getenv("KINGBASE_USER") or os.getenv("DB_USER", "ywkuser")
    password = os.getenv("KINGBASE_PASSWORD") or os.getenv("DB_PASSWORD", "123")

    if not host or not dbname or not user or not password:
        print("⚠️ 数据库连接参数未完全配置！自动降级为生成模拟数据模式。")
        return None, None

    print(f"🔌 正在连接金仓数据库 {host}:{port}/{dbname} ...")
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

        # B. 查询警情数据 (使用真实的经纬度字段名 lngofcriterion, latofcriterion)
        print("📥 正在读取 ywdata.zq_kshddpt_dsjfx_jq ...")
        sql = """
            SELECT 
                caseno,
                calltime,
                lngofcriterion,
                latofcriterion,
                neworicharasubclass,
                newcharasubclass,
                cmdid,
                cmdname,
                dutydeptno AS dutydeptna,
                dutydeptname,
                casecontents,
                replies
            FROM ywdata.zq_kshddpt_dsjfx_jq
            WHERE lngofcriterion IS NOT NULL 
              AND latofcriterion IS NOT NULL
              AND calltime >= '2026-06-01 00:00:00'
            ORDER BY calltime DESC
            LIMIT 1500
        """
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            incident_rows = cur.fetchall()
            print(f"   已抓取到 {len(incident_rows)} 条 6 月以来的真实警情数据")

            incidents = []
            for r in incident_rows:
                row_dict = dict(r)
                cleaned = clean_one(row_dict.get("replies", ""))
                row_dict.update(cleaned)
                
                # 转换坐标为 Float，跳过非数值的脏数据行
                try:
                    if row_dict["lngofcriterion"] is not None:
                        row_dict["lngofcriterion"] = float(row_dict["lngofcriterion"])
                    if row_dict["latofcriterion"] is not None:
                        row_dict["latofcriterion"] = float(row_dict["latofcriterion"])
                    incidents.append(row_dict)
                except (ValueError, TypeError):
                    continue

        return configs, incidents

    except Exception as e:
        print(f"❌ 数据库执行查询发生异常: {e}")
        return None, None
    finally:
        conn.close()

# ==========================================
# 2.5 本地离线 JSON 数据提取与清洗 (适配真实导出数据)
# ==========================================
def sync_from_local_json(assets_dir):
    local_json_path = "/mnt/c/Users/MR/Desktop/local_doc/202607/0703/wcnr_ssgl/zq_kshddpt_dsjfx_jq_202607051143.json"
    if not os.path.exists(local_json_path):
        return None, None
    
    print(f"📦 监测到本地离线 JSON 数据源: {local_json_path}")
    try:
        with open(local_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 提取第一个 key 下的列表数据
        raw_rows = list(data.values())[0]
        print(f"   读取到 {len(raw_rows)} 条离线原始数据行")
        
        # 优先从数据库中获取真实的 ywdata.case_type_config 分类配置
        configs = None
        try:
            import psycopg2
            import psycopg2.extras
            host = os.getenv("KINGBASE_HOST") or os.getenv("DB_HOST", "192.168.1.137")
            port = os.getenv("KINGBASE_PORT") or os.getenv("DB_PORT", "54321")
            dbname = os.getenv("KINGBASE_DBNAME") or os.getenv("DB_NAME", "yfywk")
            user = os.getenv("KINGBASE_USER") or os.getenv("DB_USER", "ywkuser")
            password = os.getenv("KINGBASE_PASSWORD") or os.getenv("DB_PASSWORD", "123")
            
            print("🔌 正在尝试连接数据库以读取 ywdata.case_type_config 配置...")
            conn = psycopg2.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password
            )
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT leixing, newcharasubclass_list, ay_pattern FROM ywdata.case_type_config")
                config_rows = cur.fetchall()
                configs = [dict(r) for r in config_rows]
            conn.close()
            print("📥 成功从数据库获取 ywdata.case_type_config 配置数据")
        except Exception as db_err:
            print(f"⚠️ 无法从数据库读取配置，降级尝试本地文件或模拟配置: {db_err}")
            
        if not configs:
            config_path = os.path.join(assets_dir, "case_type_config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    configs = json.load(f)
            else:
                configs = MOCK_CASE_TYPE_CONFIG
            
        incidents = []
        for r in raw_rows:
            # 坐标降级容灾：真实判定经纬度 -> 定位经纬度 -> 报警经纬度
            lng_val = r.get("lngofcriterion") or r.get("lngoflocate") or r.get("lngofcall")
            lat_val = r.get("latofcriterion") or r.get("latoflocate") or r.get("latofcall")
            
            if not lng_val or not lat_val:
                continue
                
            try:
                lng = float(lng_val)
                lat = float(lat_val)
            except (ValueError, TypeError):
                continue
                
            # 过滤超出云浮市地理范围的脏数据点 (云浮范围大概在: 东经111.0~112.6, 北纬22.3~23.4)
            if not (111.0 <= lng <= 112.6 and 22.3 <= lat <= 23.4):
                continue
                
            cleaned = clean_one(r.get("replies", ""))
            
            incident = {
                "caseno": r.get("caseno", ""),
                "calltime": r.get("calltime", ""),
                "lngofcriterion": lng,
                "latofcriterion": lat,
                "neworicharasubclass": r.get("neworicharasubclass", ""),
                "newcharasubclass": r.get("newcharasubclass", ""),
                "cmdid": r.get("cmdid", ""),
                "cmdname": r.get("cmdname", ""),
                "dutydeptna": r.get("dutydeptno") or r.get("dutydeptna", ""),
                "dutydeptname": r.get("dutydeptname", ""),
                "casecontents": r.get("casecontents", ""),
                "replies": r.get("replies", "")
            }
            incident.update(cleaned)
            incidents.append(incident)
            
        print(f"   离线清洗处理完成，共计 {len(incidents)} 条有效真实坐标警情数据")
        return configs, incidents
        
    except Exception as e:
        print(f"❌ 解析本地离线 JSON 数据发生异常: {e}")
        return None, None

# ==========================================
# 3. 入口与保存逻辑
# ==========================================
def main():
    assets_dir = os.path.join(os.path.dirname(__file__), "src", "assets")
    public_dir = os.path.join(os.path.dirname(__file__), "public")
    root_dir = os.path.dirname(__file__)

    os.makedirs(assets_dir, exist_ok=True)
    os.makedirs(public_dir, exist_ok=True)

    # 1. 优先从真实金仓数据库读取数据（生产主数据源，已成功灌入坐标修复数据）
    configs, incidents = sync_from_database()
    
    # 2. 如果数据库不可用，降级使用本地离线导出的 JSON 备份数据源
    if not incidents:
        configs, incidents = sync_from_local_json(assets_dir)

    # 3. 如果都不可用，降级生成模拟数据
    if not incidents:
        print("✨ 正在为您生成 6/1 至 7/5 包含夜间 21-23点打架斗殴的高质量模拟警情...")
        configs = MOCK_CASE_TYPE_CONFIG
        incidents = generate_mock_incidents()

    # 要写入的三个目标路径
    paths_config = [
        os.path.join(assets_dir, "case_type_config.json"),
        os.path.join(public_dir, "case_type_config.json"),
        os.path.join(root_dir, "case_type_config.json")
    ]
    paths_incidents = [
        os.path.join(assets_dir, "incidents.json"),
        os.path.join(public_dir, "incidents.json"),
        os.path.join(root_dir, "incidents.json")
    ]

    # 保存配置到各个目录
    for p in paths_config:
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(configs, f, ensure_ascii=False, indent=2)
            print(f"💾 已保存配置表: {p}")
        except Exception as e:
            print(f"⚠️ 保存配置表失败 [{p}]: {e}")

    # 保存警情到各个目录
    for p in paths_incidents:
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(incidents, f, ensure_ascii=False, indent=2)
            print(f"💾 已保存警情表: {p}")
        except Exception as e:
            print(f"⚠️ 保存警情表失败 [{p}]: {e}")

    print(f"🚀 同步与多路径写入任务圆满完成！")

if __name__ == "__main__":
    main()
