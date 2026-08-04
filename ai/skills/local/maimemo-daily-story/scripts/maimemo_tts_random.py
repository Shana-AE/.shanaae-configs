#!/usr/bin/env python3
"""
maimemo_tts_random.py — 随机选择音色为墨墨文章生成 TTS 语音。
功能：
1. 从 voice_rotation.json 随机选一个未用过的音色（全用完后重置）
2. 重启 GPT-SoVITS API 加载该音色
3. 从文章提取英文段落，生成 TTS
4. 保存 MP3 到 NAS: Documents/maimemo/YYYY/MM/DD-article_<voice>.mp3
5. 发送飞书：文章 + 单词列表 + 音频

用法：
  python3 maimemo_tts_random.py --article /tmp/maimemo-story.md --date 2026-07-03
  python3 maimemo_tts_random.py --backfill  # 回填已有文章
"""
import argparse
import json
import os
import random
import re
import subprocess
import sys
import time
import glob

GS = os.path.expanduser("~/GPT-SoVITS")
PY = f"{GS}/runtime/bin/python3"
NAS = "/Volumes/home/Documents/maimemo"
ROTATION_FILE = f"{NAS}/voice_rotation.json"
FEISHU_TO = "ou_ef08073b1540e3d078882a2b08e455bf"
TTS_API = "http://127.0.0.1:9880"
SAMPLE_TEXT = "The coastal town of Port Blakely was wrapped in an overcast sky."

def load_rotation():
    """加载轮换状态。首次运行时从 voice_list.txt 构建。"""
    if os.path.isfile(ROTATION_FILE):
        with open(ROTATION_FILE) as f:
            return json.load(f)
    # 首次：扫描 voice_list.txt 匹配实际权重文件
    voice_list_file = f"{NAS}/voice_list.txt"
    if not os.path.isfile(voice_list_file):
        print("ERROR: voice_list.txt 不存在"); sys.exit(1)
    
    voices = []
    for line in open(voice_list_file, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 格式: name_suffix (如 阿米娅_en)
        name = line.split("#")[0].strip()
        if not name:
            continue
        gpt = f"{GS}/GPT_weights_v4/{name}.ckpt"
        sov = f"{GS}/SoVITS_weights_v4/{name}.pth"
        ref = f"{GS}/voice_packs/_loli_refs/{name}/ref.wav"
        if os.path.isfile(gpt) and os.path.isfile(sov):
            ref_ok = os.path.isfile(ref)
            voices.append({"name": name, "gpt": gpt, "sov": sov, "ref": ref, "ref_ok": ref_ok})
        else:
            print(f"  跳过 {name}（权重不完整）")
    
    state = {"voices": voices, "used": [], "total": len(voices)}
    save_rotation(state)
    print(f"初始化轮换：{len(voices)} 个可用音色")
    return state

def save_rotation(state):
    with open(ROTATION_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def pick_voice(state):
    """随机选一个没用过的音色。全用完则重置。"""
    available = [v for v in state["voices"] if v["name"] not in state["used"]]
    if not available:
        print("所有音色已用完，重置轮换")
        state["used"] = []
        available = state["voices"]
    # 优先选有参考音的
    with_ref = [v for v in available if v["ref_ok"]]
    pool = with_ref if with_ref else available
    chosen = random.choice(pool)
    state["used"].append(chosen["name"])
    save_rotation(state)
    return chosen

def ensure_voice_registered(voice):
    """Idempotently register the voice's weights with the running API server
    via /register_speaker. No process kill, no port rebind, no launchctl —
    the launchd-managed server stays up the whole time and the "default"
    speaker remains available to other clients. Re-registering an already
    cached voice returns instantly. Returns True on success."""
    print(f"  register_speaker: {voice['name']}")
    result = subprocess.run(
        ["curl", "-s", "-G", f"{TTS_API}/register_speaker",
         "--data-urlencode", f"name={voice['name']}",
         "--data-urlencode", f"gpt_model_path={voice['gpt']}",
         "--data-urlencode", f"sovits_model_path={voice['sov']}",
         "--max-time", "120"],
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"  register_speaker curl 失败 (rc={result.returncode}, stderr={result.stderr.decode().strip()})")
        return False
    try:
        resp = json.loads(result.stdout.decode())
    except Exception:
        print(f"  register_speaker 响应异常: {result.stdout!r}")
        return False
    if resp.get("code") == 0:
        print(f"  register_speaker ok: {resp.get('message')}")
        return True
    print(f"  register_speaker 错误: {resp}")
    return False

def extract_english(text):
    """从文章 markdown 中提取英文段落（跳过中文、表格、frontmatter）。"""
    lines = text.split("\n")
    result = []
    in_frontmatter = False
    in_callout = False
    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            continue
        if stripped.startswith("> [!"):
            in_callout = True
            continue
        if in_callout and stripped.startswith(">"):
            continue
        if in_callout and not stripped.startswith(">"):
            in_callout = False
        # 跳过纯中文行、表格行、空行、标题
        if not stripped or stripped.startswith("|") or stripped.startswith("##"):
            continue
        if stripped.startswith("#"):
            continue
        # 跳过纯中文行
        if re.match(r'^[\u4e00-\u9fff\s\d\.\-🗑️🌀✅📊]*$', stripped):
            continue
        # 清理 markdown 标记
        clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', stripped)
        clean = re.sub(r'🗑️|🌀|✅', '', clean).strip()
        if clean and len(clean) > 10:
            result.append(clean)
    return "\n".join(result)

def generate_tts(text, ref_path, prompt_lang="en", spk="default"):
    """调用 GPT-SoVITS API 生成 TTS。spk 指定已注册的音色名（通过 /register_speaker）。"""
    prompt = {"en": "This is a voice test sample.",
              "ja": "これは音声のテストサンプルです。",
              "zh": "这是一个语音测试样本。",
              "ko": "이것은 음성 테스트 샘플입니다."}.get(prompt_lang, "This is a voice test sample.")
    
    import urllib.parse
    import subprocess as sp
    
    params = urllib.parse.urlencode({
        "refer_wav_path": ref_path,
        "prompt_text": prompt,
        "prompt_language": prompt_lang,
        "text": text[:5000],
        "text_language": "en",
        "spk": spk,
    })
    
    output = "/tmp/maimemo_tts_output.wav"
    result = sp.run(
        ["curl", "-s", "-G", TTS_API,
         "--data-urlencode", f"refer_wav_path={ref_path}",
         "--data-urlencode", f"prompt_text={prompt}",
         "--data-urlencode", f"prompt_language={prompt_lang}",
         "--data-urlencode", f"text={text[:5000]}",
         "--data-urlencode", "text_language=en",
         "--data-urlencode", f"spk={spk}",
         "-o", output, "--max-time", "600"],
        capture_output=True
    )
    if os.path.isfile(output) and os.path.getsize(output) > 5000:
        return output
    print(f"  TTS 生成失败 (curl rc={result.returncode})")
    return None

def get_lang_from_name(name):
    """从音色名推断参考音语言。"""
    if name.endswith("_ja"):
        return "ja"
    elif name.endswith("_zh"):
        return "zh"
    elif name.endswith("_ko"):
        return "ko"
    return "en"

def process_article(article_path, date_str, state):
    """为一篇文章生成 TTS。"""
    if not os.path.isfile(article_path):
        print(f"  文章不存在: {article_path}")
        return None
    
    text = open(article_path, encoding="utf-8").read()
    english = extract_english(text)
    if len(english) < 100:
        print(f"  英文内容太少 ({len(english)} 字符)，跳过")
        return None
    
    voice = pick_voice(state)
    print(f"  选音色: {voice['name']}")
    
    if not voice.get("ref_ok") or not os.path.isfile(voice["ref"]):
        print(f"  参考音不存在，跳过")
        return None
    
    lang = get_lang_from_name(voice["name"])
    
    if not ensure_voice_registered(voice):
        print(f"  音色注册失败")
        return None
    
    # 分段生成（800字/段，GET URL 的安全上限）
    chunk_size = 800
    chunks = [english[i:i+chunk_size] for i in range(0, len(english), chunk_size)]
    # 合并太短的尾段
    if len(chunks) > 1 and len(chunks[-1]) < 50:
        chunks[-2] += chunks[-1]
        chunks.pop()
    wav_files = []
    for i, chunk in enumerate(chunks):
        print(f"  生成段落 {i+1}/{len(chunks)} ({len(chunk)} 字符)...")
        wav = generate_tts(chunk, voice["ref"], lang, spk=voice["name"])
        if wav:
            # 每段重命名避免覆盖
            wav_renamed = f"/tmp/maimemo_tts_chunk_{i}.wav"
            os.rename(wav, wav_renamed)
            wav_files.append(wav_renamed)
        else:
            print(f"  段落 {i+1} 失败")
    
    # 不再 restore_api()：launchd 默认 API 全程未受影响，voice 保持缓存供下次复用
    
    if not wav_files:
        print(f"  TTS 全部失败")
        return None
    
    # 合并 + 转 MP3
    y, m, d = date_str[:4], date_str[5:7], date_str[8:10]
    out_dir = f"{NAS}/{y}/{m}"
    os.makedirs(out_dir, exist_ok=True)
    voice_name = voice["name"]
    mp3_path = f"{out_dir}/{d}-article_{voice_name}.mp3"
    
    if len(wav_files) == 1:
        wav_input = wav_files[0]
    else:
        # 用 ffmpeg 合并
        list_file = "/tmp/tts_concat.txt"
        with open(list_file, "w") as f:
            for w in wav_files:
                f.write(f"file '{w}'\n")
        merged = "/tmp/tts_merged.wav"
        subprocess.run(["/opt/homebrew/bin/ffmpeg", "-y", "-f", "concat", "-safe", "0",
                       "-i", list_file, "-c", "copy", merged],
                      capture_output=True)
        wav_input = merged
    
    subprocess.run(["/opt/homebrew/bin/ffmpeg", "-y", "-i", wav_input,
                   "-codec:a", "libmp3lame", "-b:a", "128k", mp3_path],
                  capture_output=True)
    
    if os.path.isfile(mp3_path):
        size_mb = os.path.getsize(mp3_path) / 1024 / 1024
        print(f"  ✓ MP3: {mp3_path} ({size_mb:.1f}MB)")
        return mp3_path
    return None

def send_feishu(article_path, word_list_path, audio_path, date_str):
    """发送文章 + 单词列表 + 音频到飞书。"""
    # 文章摘要
    text = open(article_path, encoding="utf-8").read()
    words = open(word_list_path, encoding="utf-8").read() if word_list_path and os.path.isfile(word_list_path) else ""
    
    voice_name = os.path.basename(audio_path).replace(".mp3", "").split("_")[-1] if audio_path else "?"
    
    msg = f"📖 墨墨文章 {date_str}\n语音: {voice_name}\n"
    if words:
        # 提取词数统计
        m = re.search(r'(\d+)/(\d+)\s*词.*?(\d+)\s*分钟', words)
        if m:
            msg += f"学习: {m.group(1)}/{m.group(2)} 词, {m.group(3)} 分钟\n"
    
    # 发文本
    subprocess.run(["openclaw", "message", "send", "--channel", "feishu",
                   "--target", FEISHU_TO, "-m", msg], capture_output=True)
    
    # 发音频
    if audio_path and os.path.isfile(audio_path):
        subprocess.run(["openclaw", "message", "send", "--channel", "feishu",
                       "--target", FEISHU_TO, "--media", audio_path], capture_output=True)
    
    print(f"  ✓ 飞书发送完成")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--article", help="文章路径")
    parser.add_argument("--date", help="日期 YYYY-MM-DD")
    parser.add_argument("--wordlist", help="单词列表路径")
    parser.add_argument("--backfill", action="store_true", help="回填已有文章")
    parser.add_argument("--no-feishu", action="store_true", help="不发飞书")
    args = parser.parse_args()
    
    state = load_rotation()
    
    if args.backfill:
        # 回填：从新到旧
        vault = os.path.expanduser("~/Developer/obsidian-vault/Inbox/ai-skills/english-learning")
        articles = []
        for root, dirs, files in os.walk(vault):
            for f in files:
                if f.startswith("MaiMemo Daily Story - ") and f.endswith(".md"):
                    m = re.search(r'(\d{4}-\d{2}-\d{2})', f)
                    if m:
                        articles.append((m.group(1), os.path.join(root, f)))
        articles.sort(key=lambda x: x[0], reverse=True)
        
        print(f"回填 {len(articles)} 篇文章（新→旧）")
        for date_str, art_path in articles:
            y, m, d = date_str[:4], date_str[5:7], date_str[8:10]
            # 检查是否已有 TTS
            existing = glob.glob(f"{NAS}/{y}/{m}/{d}-article_*.mp3")
            if existing:
                print(f"  {date_str}: 已有 TTS ({os.path.basename(existing[0])})，跳过")
                continue
            
            print(f"\n=== {date_str} ===")
            word_path = f"{NAS}/{y}/{m}/{d}.md"
            audio = process_article(art_path, date_str, state)
            if audio and not args.no_feishu:
                send_feishu(art_path, word_path, audio, date_str)
            time.sleep(5)
        
        print("\n回填完成")
    
    elif args.article and args.date:
        y, m, d = args.date[:4], args.date[5:7], args.date[8:10]
        word_path = args.wordlist or f"{NAS}/{y}/{m}/{d}.md"
        audio = process_article(args.article, args.date, state)
        if audio and not args.no_feishu:
            send_feishu(args.article, word_path, audio, args.date)
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
