import re
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse
from utils import get_exact_bucket_id

def parse_url_to_category(url, top_sites, web_categories):
    """提取 URL 域名并根据字典分类"""
    if not url: return None
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
            
        for d, name in top_sites.items():
            if domain == d or domain.endswith("." + d):
                return name
                
        for d, name in web_categories.items():
            if domain == d or domain.endswith("." + d):
                return name
    except:
        pass
    return None

def get_clean_base_name(raw_title, app_exe, special_cases):
    """提取基础应用名，优先匹配特例，并强制修正浏览器名称"""
    app_exe_lower = app_exe.lower() if app_exe else ""
    
    for exe_name, display_name in special_cases.items():
        if exe_name.lower() == app_exe_lower:
            return display_name

    browser_full_names = {
        "firefox.exe": "Mozilla Firefox",
        "chrome.exe": "Google Chrome",
        "msedge.exe": "Microsoft Edge"
    }

    clean_title = raw_title.replace('\u200b', '') if raw_title else ""
    
    if not clean_title or not clean_title.strip():
        if app_exe_lower == 'explorer.exe':
            return "Windows 桌面/任务栏"
        elif app_exe_lower in browser_full_names:
            return browser_full_names[app_exe_lower]
        else:
            return app_exe.replace('.exe', '').capitalize()
            
    parts = re.split(r'\s*[-—–|]\s*', clean_title)
    parsed_name = parts[-1].strip()

    if "\\" in parsed_name or "/" in parsed_name:
        clean_path = parsed_name.rstrip("\\/")
        parsed_name = os.path.basename(clean_path)
        
        if not parsed_name:
            parsed_name = app_exe.replace('.exe', '').capitalize()
    
    if parsed_name.lower() == "firefox" or parsed_name.lower() == "mozilla firefox":
        return "Mozilla Firefox"
    if parsed_name.lower() == "chrome" or parsed_name.lower() == "google chrome":
        return "Google Chrome"
    if parsed_name.lower() == "edge" or parsed_name.lower() == "microsoft edge":
        return "Microsoft Edge"
        
    return parsed_name if parsed_name else app_exe.replace('.exe', '').capitalize()

def get_current_status(aw, top_sites, web_categories, special_cases):
    """获取并合并当前的活跃窗口状态"""
    win_bucket = get_exact_bucket_id(aw, "aw-watcher-window_")
    afk_bucket = get_exact_bucket_id(aw, "aw-watcher-afk_")
    web_bucket = get_exact_bucket_id(aw, "aw-watcher-web-") 
    
    if not win_bucket or not afk_bucket: return None

    try:
        latest_afk = aw.get_events(afk_bucket, limit=1)
        recent_win = aw.get_events(win_bucket, limit=50)
        recent_web = aw.get_events(web_bucket, limit=100) if web_bucket else []

        is_afk = True if not latest_afk else (latest_afk[0]['data']['status'] == "afk")
        if is_afk:
            return {"status": "afk", "app": "None", "duration_seconds": 0, "last_updated": datetime.now().isoformat()}
            
        if not recent_win: return None

        def get_enriched_name(win_evt):
            app_exe = win_evt['data'].get('app', 'Unknown')
            raw_title = win_evt['data'].get('title', '')
            
            base_name = get_clean_base_name(raw_title, app_exe, special_cases)
            title_lower = raw_title.lower() if raw_title else ""
            
            if ".pdf" in title_lower:
                return f"{base_name} [本地 PDF]"
            
            is_browser = any(b in app_exe.lower() for b in ['firefox', 'chrome', 'msedge'])
            if is_browser and recent_web:
                win_ts = win_evt['timestamp']
                if isinstance(win_ts, str):
                    win_ts = datetime.fromisoformat(win_ts.replace('Z', '+00:00'))
                    
                raw_win_dur = win_evt.get('duration', 0)
                win_dur = raw_win_dur if hasattr(raw_win_dur, 'total_seconds') else timedelta(seconds=float(raw_win_dur or 0))
                win_end = win_ts + win_dur
                
                # recent_web 默认是最新的在前
                for w_evt in recent_web:
                    w_ts = w_evt['timestamp']
                    if isinstance(w_ts, str):
                        w_ts = datetime.fromisoformat(w_ts.replace('Z', '+00:00'))
                    
                    # 只看这个网页的“起始点”，是否发生在这个窗口的生命周期内。
                    # 允许 2 秒的提前量，防止 Web 插件比 Window 插件早触发几毫秒。
                    # 允许 5 秒的滞后量，防止当前窗口的结束时间还未在数据库完全更新。
                    if w_ts >= (win_ts - timedelta(seconds=2)) and w_ts <= (win_end + timedelta(seconds=5)):
                        url = w_evt['data'].get('url', '')
                        cat = parse_url_to_category(url, top_sites, web_categories)
                        if cat:
                            return f"{base_name} [{cat}]"
                        return base_name
                            
            return base_name

        current_parsed_name = get_enriched_name(recent_win[0])
        total_duration = 0.0
        
        for event in recent_win:
            e_parsed_name = get_enriched_name(event)
            if e_parsed_name == current_parsed_name:
                raw_dur = event.get('duration', 0)
                dur_sec = raw_dur.total_seconds() if hasattr(raw_dur, 'total_seconds') else float(raw_dur or 0)
                total_duration += dur_sec
            else:
                break 
                
        return {
            "status": "active", 
            "app": current_parsed_name, 
            "duration_seconds": round(total_duration, 2),
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"获取窗口状态失败: {e}")
        return None