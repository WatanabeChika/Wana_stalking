import math
from datetime import datetime, timezone, timedelta
from utils import get_exact_bucket_id

# 1 逻辑像素对应的物理毫米数。
# 基于 3072*1920 分辨率、200%缩放、16寸屏幕计算得出。
MM_PER_PIXEL = 0.224 

def get_input_stats(aw):
    """获取过去 6 小时图表数据，以及今日（本地时间 0 点起）总里程数据"""
    input_bucket = get_exact_bucket_id(aw, "aw-watcher-input_")
    if not input_bucket: return None

    # 获取带有时区信息的本地时间
    now_local = datetime.now().astimezone()
    
    # 1. 计算本地时间的当前小时整点，并转回 UTC 供查询
    current_hour_local = now_local.replace(minute=0, second=0, microsecond=0)
    current_hour_utc = current_hour_local.astimezone(timezone.utc)
    
    # 2. 计算本地时间的今天 0 点（午夜），并转回 UTC 供查询
    today_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = today_start_local.astimezone(timezone.utc)
    
    # 构建 7 个查询区间
    periods = []
    # 前 6 个：过去 6 个小时的整点区间
    for i in range(6, 0, -1):
        start = current_hour_utc - timedelta(hours=i)
        end = current_hour_utc - timedelta(hours=i-1)
        periods.append((start, end))
        
    # 第 7 个：本地今天 0 点 到 现在
    now_utc = now_local.astimezone(timezone.utc)
    periods.append((today_start_utc, now_utc))

    try:
        res = aw.query(f'RETURN = query_bucket("{input_bucket}");', periods)
        
        # 1. 整理前 6 个小时的图表数据
        hourly_stats = []
        for i in range(6):
            period_events = res[i]
            presses = sum(e['data'].get('presses', 0) for e in period_events)
            clicks = sum(e['data'].get('clicks', 0) for e in period_events)
            # 转回本地时间格式化为 HH:00 给前端显示
            time_label = periods[i][0].astimezone().strftime("%H:00")
            hourly_stats.append({"time": time_label, "presses": presses, "clicks": clicks})
            
        # 2. 计算今天全天的鼠标/滚轮真实移动物理距离
        today_events = res[6]
        total_mouse_px = 0.0
        total_scroll_px = 0.0
        
        for e in today_events:
            data = e['data']
            dx = data.get('deltaX', 0)
            dy = data.get('deltaY', 0)
            sx = data.get('scrollX', 0)
            sy = data.get('scrollY', 0)
            
            total_mouse_px += math.sqrt(dx**2 + dy**2)
            total_scroll_px += math.sqrt(sx**2 + sy**2)
            
        mouse_meters = (total_mouse_px * MM_PER_PIXEL) / 1000.0
        scroll_meters = (total_scroll_px * MM_PER_PIXEL) / 1000.0
        
        return {
            "hourly_stats": hourly_stats,
            "today_odometer": {
                "mouse_meters": round(mouse_meters, 2),
                "scroll_meters": round(scroll_meters, 2)
            }
        }
    except Exception as e:
        print(f"获取输入统计失败: {e}")
        return None