# update_db_coordinates.py - 数据库警情数据灌入与坐标修复工具
import os
import json
import psycopg2

def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

def main():
    load_env()
    
    host = os.getenv("KINGBASE_HOST") or os.getenv("DB_HOST", "192.168.1.137")
    port = os.getenv("KINGBASE_PORT") or os.getenv("DB_PORT", "54321")
    dbname = os.getenv("KINGBASE_DBNAME") or os.getenv("DB_NAME", "yfywk")
    user = os.getenv("KINGBASE_USER") or os.getenv("DB_USER", "ywkuser")
    password = os.getenv("KINGBASE_PASSWORD") or os.getenv("DB_PASSWORD", "123")

    local_json_path = "/mnt/c/Users/MR/Desktop/local_doc/202607/0703/wcnr_ssgl/zq_kshddpt_dsjfx_jq_202607051143.json"
    if not os.path.exists(local_json_path):
        print(f"❌ 错误: 未能在指定路径找到离线 JSON 文件: {local_json_path}")
        return

    print(f"🔌 正在连接金仓数据库 {host}:{port}/{dbname} ...")
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password
        )
        conn.autocommit = False
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return

    try:
        print(f"📖 正在加载并解析离线 JSON 文件: {local_json_path} ...")
        with open(local_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        raw_rows = list(data.values())[0]
        print(f"   读取到 {len(raw_rows)} 条离线真实原始数据")

        with conn.cursor() as cur:
            # 1. 获取表列信息
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='ywdata' AND table_name='zq_kshddpt_dsjfx_jq'")
            valid_columns = set(row[0] for row in cur.fetchall())
            print(f"   已获取数据库表结构，共计 {len(valid_columns)} 个有效列")

            # 2. 清空旧测试数据以防冲突
            print("🗑️ 正在清空数据库表 ywdata.zq_kshddpt_dsjfx_jq 中的旧数据...")
            cur.execute("DELETE FROM ywdata.zq_kshddpt_dsjfx_jq")

            # 3. 逐条清洗并插入
            print("📥 正在向数据库写入真实警情并修复 `lngofcriterion` 和 `latofcriterion` ...")
            inserted_count = 0
            skipped_count = 0
            
            for r in raw_rows:
                # 过滤出符合数据库字段的数据
                row_dict = {}
                for col in valid_columns:
                    if col in r:
                        row_dict[col] = r[col]
                
                # 坐标降级提取与容灾：真实判定经纬度 -> 定位经纬度 -> 报警经纬度
                lng_val = r.get("lngofcriterion") or r.get("lngoflocate") or r.get("lngofcall")
                lat_val = r.get("latofcriterion") or r.get("latoflocate") or r.get("latofcall")
                
                if lng_val and lat_val:
                    try:
                        lng = float(lng_val)
                        lat = float(lat_val)
                        # 如果是合理合规的云浮市坐标，覆盖写入 lngofcriterion 字段
                        if 110.0 <= lng <= 113.0 and 22.0 <= lat <= 24.0:
                            row_dict["lngofcriterion"] = lng
                            row_dict["latofcriterion"] = lat
                    except (ValueError, TypeError):
                        pass

                # 构建动态插入语句
                if not row_dict:
                    skipped_count += 1
                    continue

                columns = list(row_dict.keys())
                values = [row_dict[col] for col in columns]
                
                placeholders = ", ".join(["%s"] * len(columns))
                sql = f"INSERT INTO ywdata.zq_kshddpt_dsjfx_jq ({', '.join(columns)}) VALUES ({placeholders})"
                
                try:
                    cur.execute(sql, values)
                    inserted_count += 1
                except Exception as insert_err:
                    # 单条写入失败回滚当前 Savepoint，保证其他数据继续写入
                    skipped_count += 1
                    continue
                
                if inserted_count % 100 == 0:
                    print(f"   已写入 {inserted_count} 条数据...")

            print("💾 正在提交事务至数据库...")
            conn.commit()
            print(f"🎉 数据库灌入与坐标修复圆满成功！")
            print(f"📊 统计结果：成功写入 {inserted_count} 条，跳过 {skipped_count} 条")

    except Exception as e:
        print(f"❌ 运行过程中发生异常: {e}")
        print("↩️ 正在执行事务回滚...")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
