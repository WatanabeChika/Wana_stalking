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

async def fetch_media_info_async(allowlist):
    """异步调用 Windows API 获取媒体信息，包含音乐封面"""
    if not MediaManager: return None
    try:
        manager = await MediaManager.request_async()
        
        # 1. 获取系统中所有的媒体会话
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
        
        if not props.title: 
            return {"status": "stopped", "title": "", "artist": ""}
            
        # 5. 解析封面图片 (Thumbnail)
        cover_base64 = None
        # mpv 封面只会默认显示灰色
        if props.thumbnail and "mpv" not in app_id:
            try:
                stream = await props.thumbnail.open_read_async()
                reader = DataReader(stream)
                await reader.load_async(stream.size)
                cover_bytes = bytearray(stream.size)
                reader.read_bytes(cover_bytes)
                cover_base64 = "data:image/jpeg;base64," + base64.b64encode(cover_bytes).decode('utf-8')
            except Exception as e:
                print(f"提取封面失败: {e}")
                
        return {
            "status": "playing" if is_playing else "paused",
            "app_id": app_id,
            "title": props.title,
            "artist": props.artist if props.artist else "未知歌手",
            "cover_base64": cover_base64,
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"提取媒体数据失败: {e}")
        return None

def get_music_status(allowlist):
    """同步包裹入口"""
    return asyncio.run(fetch_media_info_async(allowlist))