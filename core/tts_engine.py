import asyncio
import os
import subprocess
import tempfile
import time
import uuid
import wave
import re
import threading
import edge_tts
from core.config import logger, MPV_EXE, PIPER_EXE, PIPER_DIR, HYBRID_THRESHOLD, load_app_config

CREATE_NO_WINDOW = 0x08000000

# 集中管理活跃的子进程，防止僵尸进程
_active_processes = []
_process_lock = threading.Lock()
_pygame_lock = threading.Lock()

def _add_process(p):
    with _process_lock:
        _active_processes.append(p)

def _remove_process(p):
    with _process_lock:
        if p in _active_processes:
            _active_processes.remove(p)

def cleanup_tts_processes():
    """退出应用时清理所有正在运行的TTS进程"""
    with _process_lock:
        for p in _active_processes:
            try:
                p.terminate()
            except Exception:
                pass
        _active_processes.clear()

def _play_audio_file(audio_path):
    """使用 pygame 播放本地音频文件，作为 mpv 不存在时的兜底方案。"""
    with _pygame_lock:
        import pygame

        pygame.mixer.init()
        try:
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
            pygame.mixer.music.unload()
        finally:
            pygame.mixer.quit()

def play_voice_worker(text, status_signal=None):
    """
    运行在子线程中的TTS逻辑。
    根据文本长度决定使用 Edge-TTS (云端) 还是 Piper (本地)。
    """
    if not text:
        return

    def send_status(msg):
        if status_signal:
            status_signal.emit(msg)

    # 我们直接把标点符号前缀的逻辑干掉，因为底层拼接已经足够可靠了，且避免前缀被Piper误伤
    safe_text_for_speech = text
    
    config = load_app_config()
    use_local_tts = config.get("USE_LOCAL_TTS", True)

    use_cloud = len(text) > HYBRID_THRESHOLD or not use_local_tts

    try:
        send_status("⏳ 准备中...")
        if use_cloud:
            send_status("☁️ 云端连接...")
            # 智能判断语言并选择最顶级的发音人
            has_chinese_global = bool(re.search(r'[\u4e00-\u9fff]', text))
            voice_name = "zh-CN-XiaoxiaoNeural" if has_chinese_global else "en-US-AriaNeural"

            async def stream_edge():
                send_status("✨ AI合成中...")
                communicate = edge_tts.Communicate(
                    text=safe_text_for_speech, 
                    voice=voice_name,
                    rate="-10%",
                    volume="+50%",
                    pitch="+0Hz"
                )
                first_chunk = True

                if MPV_EXE.exists():
                    # 启动 mpv 接收 stdin 数据，并加上音频增强参数
                    player_process = subprocess.Popen(
                        [
                            str(MPV_EXE),
                            "--no-terminal",
                            "--force-window=no",
                            "--audio-buffer=0.5",     # 给云端流媒体充足的缓冲
                            "--volume=130",           # 强行放大基础音量
                            "--af=acompressor",       # 使用 ffmpeg 内置的音频压缩器防爆音
                            "-"
                        ],
                        stdin=subprocess.PIPE,
                        creationflags=CREATE_NO_WINDOW,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    _add_process(player_process)

                    try:
                        async for chunk in communicate.stream():
                            if chunk["type"] == "audio":
                                if first_chunk:
                                    send_status("▶️ 开始朗读...")
                                    first_chunk = False
                                player_process.stdin.write(chunk["data"])
                                player_process.stdin.flush()
                    except Exception as e:
                        logger.error(f"Edge TTS 流式传输错误: {e}")
                    finally:
                        player_process.stdin.close()
                        player_process.wait()
                        _remove_process(player_process)
                else:
                    send_status("✨ AI合成中...")
                    cloud_audio = os.path.join(tempfile.gettempdir(), f"maoboshot_edge_{uuid.uuid4().hex}.mp3")
                    try:
                        await communicate.save(cloud_audio)
                        send_status("▶️ 开始朗读...")
                        _play_audio_file(cloud_audio)
                    finally:
                        try:
                            if os.path.exists(cloud_audio):
                                os.remove(cloud_audio)
                        except Exception:
                            pass

            asyncio.run(stream_edge())

        else:
            send_status("⚡ 播放中...")
            
            # 本地 Piper TTS
            model_cn = PIPER_DIR / "zh_CN-huayan-medium.onnx"
            model_en = PIPER_DIR / "en_US-lessac-medium.onnx"
            cache_dir = tempfile.gettempdir()
            temp_wav = os.path.join(cache_dir, f"maoboshot_tts_{uuid.uuid4().hex}.wav")
            silence_wav = os.path.join(cache_dir, "maoboshot_silence_0.5s.wav")

            # 确保存在空白音音频
            if not os.path.exists(silence_wav):
                try:
                    with wave.open(silence_wav, 'wb') as f:
                        f.setnchannels(1)
                        f.setsampwidth(2)
                        f.setframerate(22050)
                        f.writeframes(b'\x00' * int(22050 * 0.5 * 2))
                except Exception as e:
                    logger.error(f"无法生成 silence_wav: {e}")

            has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
            current_model = model_cn if has_chinese else model_en
            if not current_model.exists():
                current_model = model_cn

            safe_text = "，" + text
            
            if PIPER_EXE.exists():
                cmd_gen = [str(PIPER_EXE), "--model", str(current_model), "--length_scale", "1.15", "--output_file", temp_wav]
                p_gen = subprocess.Popen(cmd_gen, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
                _add_process(p_gen)
                
                p_gen.communicate(input=safe_text.encode('utf-8'))
                _remove_process(p_gen)
                
                if os.path.exists(temp_wav):
                    cmd_play = [
                        str(MPV_EXE), 
                        "--no-terminal", 
                        "--force-window=no", 
                        "--audio-buffer=0.2",
                        "--volume=130",       # 本地引擎也放大基础音量
                        "--af=acompressor"    # 加上防爆音动态压缩
                    ]
                    if os.path.exists(silence_wav):
                        cmd_play.append(silence_wav)
                    cmd_play.append(temp_wav)
                    
                    if MPV_EXE.exists():
                        p_play = subprocess.Popen(cmd_play, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
                        _add_process(p_play)
                        p_play.wait()
                        _remove_process(p_play)
                    else:
                        _play_audio_file(temp_wav)
            else:
                logger.error("❌ 错误：找不到 Piper.exe")

    except Exception as e:
        logger.error(f"播放出错: {e}", exc_info=True)
        send_status("❌ 出错")
    finally:
        try:
            if "temp_wav" in locals() and os.path.exists(temp_wav):
                os.remove(temp_wav)
        except Exception:
            pass
        send_status("reset")
