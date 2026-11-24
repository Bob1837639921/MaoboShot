import asyncio
import base64
import os
import subprocess
import tempfile
import time
import uuid
import wave
import re
import threading
from urllib.parse import urljoin
import edge_tts
import requests
from core.config import logger, MPV_EXE, PIPER_EXE, PIPER_DIR, HYBRID_THRESHOLD, load_app_config

CREATE_NO_WINDOW = 0x08000000

# 集中管理活跃的子进程，防止僵尸进程
_active_processes = []
_process_lock = threading.Lock()
_pygame_lock = threading.Lock()
_audio_subsystem_lock = threading.Lock()

# 播放代次：每次开始朗读或主动打断都会递增，旧代次的朗读据此自行退出
_playback_lock = threading.Lock()
_playback_generation = 0
_latest_worker_generation = 0

def _begin_playback():
    global _playback_generation, _latest_worker_generation
    with _playback_lock:
        _playback_generation += 1
        _latest_worker_generation = _playback_generation
        return _playback_generation

def _is_current_playback(generation):
    return generation == _playback_generation

def _make_status_sender(status_signal, generation):
    """过期朗读不再更新界面；但被打断且没有新朗读接替时，仍需发出 reset 复位按钮。"""
    def send_status(msg):
        if not status_signal:
            return
        if msg == "reset":
            if generation == _latest_worker_generation:
                status_signal.emit(msg)
        elif _is_current_playback(generation):
            status_signal.emit(msg)
    return send_status

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

def stop_tts_playback():
    """停止当前的语音合成与播放（mpv/Piper 子进程与 pygame 播放循环）"""
    global _playback_generation
    logger.info("主动打断当前语音朗读进程")
    with _playback_lock:
        _playback_generation += 1
    cleanup_tts_processes()

def list_audio_output_devices():
    try:
        import pygame
        from pygame._sdl2 import sdl2
        from pygame._sdl2.audio import get_audio_device_names

        # Enumerating only needs SDL audio, even when no default device can open.
        with _audio_subsystem_lock:
            if pygame.mixer.get_init():
                return get_audio_device_names(False)
            sdl2.init_subsystem(sdl2.INIT_AUDIO)
            try:
                return get_audio_device_names(False)
            finally:
                pygame.mixer.quit()
    except (ImportError, RuntimeError, OSError) as error:
        logger.warning("无法列出音频输出设备: %s", error)
        return None


def _play_audio_file(audio_path, generation=None):
    """使用 pygame 播放本地音频文件，作为 mpv 不存在时的兜底方案。若 pygame 缺失则尝试用内置 winsound 播放 wav 文件。"""
    with _pygame_lock:
        if generation is not None and not _is_current_playback(generation):
            return
        try:
            import pygame
            device = load_app_config().get("AUDIO_OUTPUT_DEVICE")
            with _audio_subsystem_lock:
                if device:
                    try:
                        pygame.mixer.init(devicename=device)
                    except pygame.error:
                        logger.warning("指定的朗读输出设备不可用，改用 Windows 默认设备")
                        pygame.mixer.init()
                else:
                    pygame.mixer.init()
            try:
                pygame.mixer.music.load(audio_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    if generation is not None and not _is_current_playback(generation):
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.05)
                pygame.mixer.music.unload()
            finally:
                with _audio_subsystem_lock:
                    pygame.mixer.quit()
        except Exception as e:
            logger.warning(f"pygame 播放失败或未安装: {e}")
            # 如果是 wav 文件，尝试使用内置 winsound 播放 (零依赖)
            if str(audio_path).lower().endswith(".wav"):
                if generation is not None and not _is_current_playback(generation):
                    return
                try:
                    import winsound
                    winsound.PlaySound(str(audio_path), winsound.SND_FILENAME)
                except Exception as e2:
                    logger.error(f"winsound 播放失败: {e2}")
            else:
                logger.error("pygame 播放失败，且音频格式非 WAV，无法进行兜底播放。")

def _looks_like_base64(value):
    if not isinstance(value, str) or len(value) < 80:
        return False
    clean = value.strip()
    if clean.startswith("data:") and ";base64," in clean:
        return True
    return bool(re.fullmatch(r"[A-Za-z0-9+/=\s]+", clean))

def _decode_audio_base64(value):
    clean = value.strip()
    if clean.startswith("data:") and ";base64," in clean:
        clean = clean.split(";base64,", 1)[1]
    return base64.b64decode(clean)

def _find_audio_payload(data):
    if isinstance(data, dict):
        for key in ("audio", "b64_json", "base64", "audio_base64", "data", "url"):
            value = data.get(key)
            if isinstance(value, str):
                if key == "url" or value.startswith(("http://", "https://")):
                    return ("url", value)
                if _looks_like_base64(value):
                    return ("base64", value)
        for value in data.values():
            found = _find_audio_payload(value)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_audio_payload(item)
            if found:
                return found
    return None

def _play_custom_tts(text, config, send_status, generation=None):
    base_url = config["TTS_BASE_URL"]
    model = config["TTS_MODEL"]
    voice = config["TTS_VOICE"]
    style = config["TTS_STYLE"]
    if not base_url.startswith(("https://", "http://")) or not model or not voice:
        raise RuntimeError("请填写语音服务地址、模型和音色")
    
    headers = {}
    api_key = config["TTS_API_KEY"]
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    if config["TTS_API_FORMAT"] == "chat":
        route = "chat/completions"
        messages = []
        if style and re.match(r"^\s*[\(\uff08\[][^)\uff09\]]+[\)\uff09\]]", style):
            text = f"{style}{text}"
        elif style:
            messages.append({"role": "user", "content": style})
        messages.append({"role": "assistant", "content": text})
        payload = {"model": model, "messages": messages, "audio": {"format": "wav", "voice": voice}}
        if api_key:
            headers["api-key"] = api_key
    else:
        route = "audio/speech"
        payload = {"model": model, "input": text, "voice": voice, "response_format": "wav"}
        if style:
            payload["instructions"] = style

    endpoint = urljoin(base_url.rstrip("/") + "/", route)
    send_status("✨ 语音合成中...")
    response = requests.post(
        endpoint,
        headers=headers,
        json=payload,
        timeout=45
    )

    content_type = response.headers.get("content-type", "")
    if response.status_code >= 400:
        raise RuntimeError(f"语音服务请求失败（HTTP {response.status_code}）")

    audio_path = os.path.join(tempfile.gettempdir(), f"maoboshot_speech_{uuid.uuid4().hex}.wav")
    try:
        if content_type.startswith(("audio/", "application/octet-stream")):
            audio_bytes = response.content
        else:
            payload = response.json()
            found = _find_audio_payload(payload)
            if not found:
                raise RuntimeError("语音服务未返回音频")
            kind, value = found
            if kind == "url":
                audio_response = requests.get(value, timeout=45)
                audio_response.raise_for_status()
                audio_bytes = audio_response.content
            else:
                audio_bytes = _decode_audio_base64(value)

        with open(audio_path, "wb") as f:
            f.write(audio_bytes)
        if generation is not None and not _is_current_playback(generation):
            return
        send_status("▶️ 开始朗读...")
        player_engine = config.get("AUDIO_PLAYER", "pygame")
        if player_engine == "mpv" and MPV_EXE.exists():
            cmd_play = [
                str(MPV_EXE), 
                "--no-terminal", 
                "--force-window=no", 
                "--audio-buffer=0.2",
                "--volume=130",
                "--af=acompressor",
                audio_path
            ]
            p_play = subprocess.Popen(cmd_play, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
            _add_process(p_play)
            p_play.wait()
            _remove_process(p_play)
        else:
            _play_audio_file(audio_path, generation)
    finally:
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception:
            pass

def play_voice_worker(text, status_signal=None):
    """
    运行在子线程中的TTS逻辑。
    根据文本长度决定使用 Edge-TTS (云端) 还是 Piper (本地)。
    """
    if not text:
        return

    generation = _begin_playback()
    send_status = _make_status_sender(status_signal, generation)

    def preprocess_text_for_speech(t, add_prefix=False):
        if not t:
            return t
        # 拆分驼峰命名法 (e.g. setStyleSheet -> set Style Sheet)
        t = re.sub(r'([a-z])([A-Z])', r'\1 \2', t)
        # 将字母之间的连字符和下划线替换为空格 (e.g. hello-world -> hello world, foo_bar -> foo bar)
        t = re.sub(r'([a-zA-Z])[-_]+([a-zA-Z])', r'\1 \2', t)
        if add_prefix:
            # 在文本最前面插入一个静默标点，防止 TTS 引擎/音频设备初始化时吃掉第一个音节
            has_zh = bool(re.search(r'[\u4e00-\u9fff]', t))
            t = ('，' if has_zh else ', ') + t
        return t

    # Edge 的开头留一小段停顿，避免音频设备初始化时裁掉首音节。
    safe_text_for_speech = preprocess_text_for_speech(text, add_prefix=True)
    
    config = load_app_config()
    use_local_tts = config.get("USE_LOCAL_TTS", True)
    ai_tts_provider = config.get("AI_TTS_PROVIDER", "edge")

    use_cloud = len(text) > HYBRID_THRESHOLD or not use_local_tts
    
    if not use_cloud and not PIPER_EXE.exists():
        logger.warning("未检测到本地 Piper.exe，已自动降级为云端语音合成")
        use_cloud = True

    try:
        send_status("⏳ 准备中...")
        if use_cloud:
            send_status("☁️ 云端连接...")
            if ai_tts_provider == "custom":
                _play_custom_tts(preprocess_text_for_speech(text), config, send_status, generation)
                return

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

                player_engine = config.get("AUDIO_PLAYER", "pygame")
                if player_engine == "mpv" and MPV_EXE.exists():
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
                            if not _is_current_playback(generation):
                                break
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
                        if not _is_current_playback(generation):
                            return
                        send_status("▶️ 开始朗读...")
                        _play_audio_file(cloud_audio, generation)
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

            # Piper 已经通过 preprocess_text_for_speech(add_prefix=True) 加了前缀，直接使用
            safe_text = safe_text_for_speech
            
            if PIPER_EXE.exists():
                cmd_gen = [str(PIPER_EXE), "--model", str(current_model), "--length_scale", "1.15", "--output_file", temp_wav]
                p_gen = subprocess.Popen(cmd_gen, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
                _add_process(p_gen)
                
                p_gen.communicate(input=safe_text.encode('utf-8'))
                _remove_process(p_gen)

                if not _is_current_playback(generation):
                    return

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
                    
                    player_engine = config.get("AUDIO_PLAYER", "pygame")
                    if player_engine == "mpv" and MPV_EXE.exists():
                        p_play = subprocess.Popen(cmd_play, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
                        _add_process(p_play)
                        p_play.wait()
                        _remove_process(p_play)
                    else:
                        _play_audio_file(temp_wav, generation)
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
