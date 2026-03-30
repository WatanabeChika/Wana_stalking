import asyncio
from datetime import datetime

try:
    from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager
except ImportError:
    print("缺少 winsdk 库，请在终端运行: pip install winsdk")
    MediaManager = None

async def fetch_media_info_async(allowlist):
    """异步调用 Windows API 获取媒体信息"""
    if not MediaManager: return None
    try:
        manager = await MediaManager.request_async()
        
        # 1. 获取系统中所有的媒体会话，而不是只获取当前焦点
        sessions = manager.get_sessions()
        if not sessions: return {"status": "stopped", "title": "", "artist": ""}

        # 2. 筛选出在白名单里的设备
        valid_sessions = []
        for session in sessions:
            if not session: continue
            app_id = session.source_app_user_model_id.lower()
            if any(allowed_app in app_id for allowed_app in allowlist):
                valid_sessions.append(session)

        # 如果没有白名单设备，直接判定为休眠
        if not valid_sessions:
            return {"status": "stopped", "title": "", "artist": ""}

        # 3. 仲裁逻辑
        selected_session = valid_sessions[0]
        if len(valid_sessions) > 1:
            current_session = manager.get_current_session()
            curr_app_id = current_session.source_app_user_model_id.lower() if current_session else ""
            
            # 条件 A：如果系统的当前焦点恰好在白名单里，说明它是最近刚操作过的，优先用它
            matched_current = next((s for s in valid_sessions if s.source_app_user_model_id.lower() == curr_app_id), None)
            
            if matched_current:
                selected_session = matched_current
            else:
                # 条件 B：如果系统焦点被浏览器等非白名单应用抢走了，那么在白名单里优先挑正在播放的
                playing_session = next((s for s in valid_sessions if s.get_playback_info().playback_status == 4), None)
                if playing_session:
                    selected_session = playing_session
                # 如果都没在播放，就默认保持 selected_session 为列表第一个

        # 4. 解析选中的最终 session
        app_id = selected_session.source_app_user_model_id.lower()
        info = selected_session.get_playback_info()
        is_playing = (info.playback_status == 4)
        props = await selected_session.try_get_media_properties_async()
        
        if not props.title: 
            return {"status": "stopped", "title": "", "artist": ""}
            
        return {
            "status": "playing" if is_playing else "paused",
            "app_id": app_id,
            "title": props.title,
            "artist": props.artist if props.artist else "未知歌手",
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"提取媒体数据失败: {e}")
        return None

def get_music_status(allowlist):
    """同步包裹入口"""
    return asyncio.run(fetch_media_info_async(allowlist))