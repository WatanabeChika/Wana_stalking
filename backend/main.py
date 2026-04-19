import time
from datetime import datetime
from aw_client import ActivityWatchClient
import firebase_admin
from firebase_admin import credentials, db

from collector_window import get_current_status
from collector_input import get_input_stats
from collector_music import get_music_status

FIREBASE_KEY_PATH = "wanakachi-monitoring-firebase-adminsdk-fbsvc-01b51930a9.json" 
FIREBASE_DB_URL = "https://wanakachi-monitoring-default-rtdb.asia-southeast1.firebasedatabase.app/" 

# 轮询刷新频率
UPDATE_INTERVAL = 3  
# 心跳强制同步频率
FORCE_SYNC_INTERVAL = 60 

MUSIC_APP_ALLOWLIST = [
    "musicplayer2", "mpv", "spotify", "cloudmusic", "qqmusic", 
]

TOP_SITES = {
    "bilibili.com": "Bilibili",
    "shuiyuan.sjtu.edu.cn": "SJTU 水源社区",
    "tieba.baidu.com": "百度贴吧",
    "twitter.com": "X",
    "x.com": "X",
    "youtube.com": "YouTube",
    "github.com": "GitHub",
    "bgm.tv": "Bangumi",
    "bangumi.tv": "Bangumi",
    "gemini.google.com": "Google Gemini",
    "moegirl.icu": "萌娘百科",
    "moegirl.org.cn": "萌娘百科",
    "app.flowoss.com": "Flow - epub 阅读器",
}

WEB_CATEGORIES = {
    "oc.sjtu.edu.cn": "SJTU 校园网",
    "mail.sjtu.edu.cn": "SJTU 校园网",
    "i.sjtu.edu.cn": "SJTU 校园网",
    "yjs.sjtu.edu.cn": "SJTU 校园网",
    "cnmooc.sjtu.cn": "SJTU 校园网",
    "course.sjtu.plus": "SJTU 校园网",
    "pan.sjtu.edu.cn": "SJTU 校园网",
    "my.sjtu.edu.cn": "SJTU 校园网",
    "v.sjtu.edu.cn": "SJTU 校园网",
    
    "siliconflow.cn": "AI 大模型",
    "aihubmix.com": "AI 大模型",
    "bianxie.ai": "AI 大模型",
    "aistudio.google.com": "AI 大模型",
    "notebooklm.google.com": "AI 大模型",
    "grok.com": "AI 大模型",
    "chatgpt.com": "AI 大模型",
    "deepseek.com": "AI 大模型",
    "qwen.ai": "AI 大模型",
    "kimi.com": "AI 大模型",
    "doubao.com": "AI 大模型",

    "mikanani.me": "ACG 相关",
    "nyaa.si": "ACG 相关",
    "sukebei.nyaa.si": "ACG 相关",
    "dmhy.org": "ACG 相关",
    "acg.rip": "ACG 相关",
    "xfani.com": "ACG 相关",
    "omofuns.xyz": "ACG 相关",
    "touchgal.top": "ACG 相关",
    "vcb-s.com": "ACG 相关",
    "acgrip.com": "ACG 相关",
    "wenku8.net": "ACG 相关",
    "pixiv.net": "ACG 相关",
    "saucenao.com": "ACG 相关",
    "acgndog.com": "ACG 相关",
}

WINDOW_TITLE_SPECIAL_CASES = {
    "cloudmusic.exe"         : "网易云音乐",
    "Adobe Premiere Pro.exe" : "Adobe Premiere Pro",
    "portal2.exe"            : "Portal 2",
    "aw-qt.exe"              : "ActivityWatch",
    "Human.exe"              : "Human: Fall Flat",
    "WindowsTerminal.exe"    : "Windows Terminal",
    "NeeView.exe"            : "NeeView",
}

# 1. 初始化 Firebase
try:
    cred = credentials.Certificate(FIREBASE_KEY_PATH)
    firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
except Exception as e:
    print(f"Firebase 初始化失败，请检查密钥路径: {e}")

# 2. 初始化 ActivityWatch 客户端
aw = ActivityWatchClient("status-pusher", testing=False)

# 3. Firebase 推送助手函数
def push_to_firebase(node_name, data, log_msg=None):
    try:
        db.reference(node_name).set(data)
        if log_msg: print(log_msg)
    except Exception as e:
        print(f"推送 {node_name} 失败: {e}")

# 4. 主循环引擎
if __name__ == "__main__":
    print(f"🚀 启动全方位状态监听服务...")
    
    # 初始化状态缓存字典
    last_app_sig = ""
    last_music_sig = ""
    last_force_sync_time = time.time()
    last_input_update_hour = -1

    while True:
        current_time = time.time()
        # 检查是否到了 60 秒强制同步的时间
        is_force_sync = (current_time - last_force_sync_time) > FORCE_SYNC_INTERVAL

        # A. 窗口与 Web 状态
        current_status = get_current_status(aw, TOP_SITES, WEB_CATEGORIES, WINDOW_TITLE_SPECIAL_CASES)
        if current_status: 
            # 生成当前状态的“特征指纹” (只要软件名和活跃状态不变，指纹就不变)
            app_sig = f"{current_status['app']}_{current_status['status']}"
            
            if is_force_sync or app_sig != last_app_sig:
                push_to_firebase('now_playing', current_status)
                last_app_sig = app_sig

        # B. 媒体音乐状态
        current_music = get_music_status(MUSIC_APP_ALLOWLIST)
        if current_music:
            # 音乐特征指纹：状态(播放/暂停) + 歌名 + 歌手
            music_sig = f"{current_music['status']}_{current_music['title']}_{current_music['artist']}"
            
            if is_force_sync or music_sig != last_music_sig:
                push_to_firebase('music_status', current_music)
                last_music_sig = music_sig
                
        # 重置心跳计时器
        if is_force_sync:
            last_force_sync_time = current_time

        # C. 整点键鼠统计 (低频任务，逻辑不变)
        current_hour = datetime.now().hour
        if current_hour != last_input_update_hour:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 触发整点统计，拉取并推送键鼠数据...")
            input_stats = get_input_stats(aw)
            if input_stats:
                # 将小时数据和里程计数据分别打包推送
                push_to_firebase('input_history', {
                    "last_updated": datetime.now().isoformat(),
                    "data": input_stats["hourly_stats"],
                    "odometer": input_stats["today_odometer"]
                }, log_msg=f"✅ 成功推送键鼠数据 | 今日鼠标已滑行: {input_stats['today_odometer']['mouse_meters']} 米")
            last_input_update_hour = current_hour

        time.sleep(UPDATE_INTERVAL)