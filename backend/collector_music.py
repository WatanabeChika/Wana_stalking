import asyncio
import base64
from datetime import datetime

try:
    from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager
    from winsdk.windows.storage.streams import DataReader
except ImportError:
    print("缺少 winsdk 库，请在终端运行: pip install winsdk")
    MediaManager = None
    DataReader = None

# 全局缓存
_cached_manager = None
_last_song_id = None
_cached_cover_base64 = None

async def fetch_media_info_async(allowlist):
    """异步调用 Windows API 获取媒体信息，包含音乐封面"""
    global _cached_manager, _last_song_id, _cached_cover_base64
    
    if not MediaManager: return None

    try:
        # 只有在第一次运行，或者底层服务崩溃时，才去请求 manager
        if _cached_manager is None:
            _cached_manager = await MediaManager.request_async()
            
        manager = _cached_manager

        # 1. 获取系统中所有的媒体会话
        sessions = manager.get_sessions()
        if not sessions: 
            return {"status": "stopped", "title": "", "artist": ""}

        # 2. 筛选白名单设备
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
            
            matched_current = next((s for s in valid_sessions if s.source_app_user_model_id.lower() == curr_app_id), None)
            
            if matched_current:
                selected_session = matched_current
            else:
                playing_session = next((s for s in valid_sessions if s.get_playback_info().playback_status == 4), None)
                if playing_session:
                    selected_session = playing_session

        # 4. 解析选中的最终 session 及基础信息
        app_id = selected_session.source_app_user_model_id.lower()
        info = selected_session.get_playback_info()
        is_playing = (info.playback_status == 4)
        props = await selected_session.try_get_media_properties_async()
        
        title = props.title
        artist = props.artist if props.artist else "未知歌手"
        
        if not title: 
            return {"status": "stopped", "title": "", "artist": ""}
            
        # 切歌检测。如果歌名和歌手没变，直接使用上次算好的 Base64 封面
        current_song_id = f"{title}_{artist}"
        
        if current_song_id != _last_song_id:
            # 只有发现“切歌”了，才重新提取并计算封面
            _last_song_id = current_song_id
            _cached_cover_base64 = None 
            
            if props.thumbnail and "mpv" not in app_id:
                try:
                    stream = await props.thumbnail.open_read_async()
                    reader = DataReader(stream)
                    await reader.load_async(stream.size)
                    cover_bytes = bytearray(stream.size)
                    reader.read_bytes(cover_bytes)
                    _cached_cover_base64 = "data:image/jpeg;base64," + base64.b64encode(cover_bytes).decode('utf-8')
                except Exception as e:
                    print(f"提取封面失败: {e}")
                
        return {
            "status": "playing" if is_playing else "paused",
            "app_id": app_id,
            "title": title,
            "artist": artist,
            "cover_base64": _cached_cover_base64,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"提取媒体数据失败: {e}")
        # 如果出现异常（比如底层 NPSM 服务重启），清空缓存的 manager，下次强制重新获取
        _cached_manager = None
        return None

def get_music_status(allowlist):
    """同步包裹入口"""
    return asyncio.run(fetch_media_info_async(allowlist))