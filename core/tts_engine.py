import asyncio
import os
import subprocess
import wave
import re
import threading
import edge_tts
from core.config import logger, MPV_EXE, PIPER_EXE, PIPER_DIR, HYBRID_THRESHOLD, load_app_config

CREATE_NO_WINDOW = 0x08000000

# 集中管理活跃的子进程，防止僵尸进程
_active_processes = []
_process_lock = threading.Lock()

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
            
            # 启动 mpv 接收 stdin 数据，并加上音频增强参数
            player_process = subprocess.Popen(
                [
                    str(MPV_EXE), 
                    "--no-terminal", 
                    "--force-window=no", 
                    "--audio-buffer=0.5",     # 给云端流媒体充足的缓冲
                    "--af=lavfi=[loudnorm]",  # 使用ffmpeg响度标准化滤镜，让人声更饱满清晰
                    "-"
                ],
                stdin=subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            _add_process(player_process)

            async def stream_edge():
                send_status("✨ AI合成中...")
                communicate = edge_tts.Communicate(
                    text=safe_text_for_speech, 
                    voice=voice_name,
                    rate="+0%",
                    volume="+10%",
                    pitch="+0Hz"
                )
                first_chunk = True
                
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

            asyncio.run(stream_edge())

        else:
            send_status("⚡ 播放中...")
            
            # 本地 Piper TTS
            model_cn = PIPER_DIR / "zh_CN-huayan-medium.onnx"
            model_en = PIPER_DIR / "en_US-lessac-medium.onnx"
            temp_wav = PIPER_DIR / "temp_speech.wav"
            silence_wav = PIPER_DIR / "silence_0.5s.wav"

            # 确保存在空白音音频
            if not silence_wav.exists():
                try:
                    with wave.open(str(silence_wav), 'wb') as f:
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
                cmd_gen = [str(PIPER_EXE), "--model", str(current_model), "--output_file", str(temp_wav)]
                p_gen = subprocess.Popen(cmd_gen, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
                _add_process(p_gen)
                
                p_gen.communicate(input=safe_text.encode('utf-8'))
                _remove_process(p_gen)
                
                if temp_wav.exists():
                    cmd_play = [str(MPV_EXE), "--no-terminal", "--force-window=no", "--audio-buffer=0.2"]
                    if silence_wav.exists():
                        cmd_play.append(str(silence_wav))
                    cmd_play.append(str(temp_wav))
                    
                    p_play = subprocess.Popen(cmd_play, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
                    _add_process(p_play)
                    p_play.wait()
                    _remove_process(p_play)
            else:
                logger.error("❌ 错误：找不到 Piper.exe")

    except Exception as e:
        logger.error(f"播放出错: {e}", exc_info=True)
        send_status("❌ 出错")
    finally:
        send_status("reset")
