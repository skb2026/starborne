#!/usr/bin/env python3
import json
import os
import random
import re
import sys
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path

STATE_PATH = Path.home() / ".openclaw" / "workspace" / "starborne"
WAREHOUSE_FILE = STATE_PATH / "warehouse.json"
ICON_DIR = STATE_PATH / "images" / "icons"
FULL_DIR = STATE_PATH / "images" / "full"

RARITY_INFO = [
    ("普通废料", 0.50, 0, 4999, "⬜"),
    ("魔法精制", 0.30, 50000, 52999, "🔵"),
    ("稀有古物", 0.13, 80000, 81299, "🟡"),
    ("传奇星核", 0.05, 93000, 93499, "🟠"),
    ("太古沙丘", 0.015, 98000, 98149, "🟢"),
    ("太初虚空", 0.005, 99500, 99549, "🔴"),
]
RARITY_ORDER = [info[0] for info in RARITY_INFO]
RARITY_INDEX = {name: idx for idx, name in enumerate(RARITY_ORDER)}
SPECIAL_VOID = {
    99536: ("Arrakeen's Voidclaw", "阿拉基恩虚空爪"),
    99537: ("Fremen Hollow Blade - \"Maidenless\"", "弗雷曼无女剑 - “无巫女”"),
}
SUPPLIES = [
    ("合成蛋白块", 25),
    ("香料精华胶囊", 30),
    ("沙虫肉干", 22),
    ("低温休眠营养液", 18),
    ("辐射净化药剂", 20),
    ("弗雷曼蜜露", 28),
    ("黑市反重力酒", 35),
    ("基地回收能量棒", 30),
]

PREFIXES = [
    "碎星的", "深渊的", "沙海的", "香料染的", "虚空的", "虫巢的", "基地最后的",
    "流亡者的", "起源舰的", "终焉的", "伊克斯的", "柯拉尔的", "弗雷曼的", "哈克南的", "阿崔迪的",
]
MODIFIERS = [
    "脉冲", "量子", "沙暴", "香料浸", "虫甲", "力场", "反物质", "神经", "辐射", "冰晶", "烈阳", "蚀刻",
]
BASE_MODULES = [
    "脉冲步枪", "离子刃", "相移护甲", "外骨骼", "神经头盔", "重型护盾", "沙行靴", "香料探测器",
    "悬浮战车", "力场发生器", "虫巢护符", "星舰核心", "遗迹数据板", "反重力腰带", "轨道戒指",
]
COMMON_NAMES = [
    "损坏推进器", "废弃控制板", "腐蚀线圈", "老化外壳", "裂纹护罩", "锈蚀齿轮", "断裂光纤", "残留反应堆",
    "破碎舱门", "裂变电池"
]
ENGLISH_PREFIXES = [
    "Quantum", "Void", "Dune", "Spice", "Worm", "Voidclaw", "Ancient", "Fremen", "Nebula", "Starforge",
]
ENGLISH_MODIFIERS = [
    "Pulse", "Heavy", "Eternal", "Annihilation", "Resonant", "Abyssal", "Arc", "Phantom", "Radiant", "Warp",
]
ENGLISH_BASE = [
    "Relic Armor", "Void Blade", "Core", "Field Generator", "Bond", "Harbinger", "Exoskeleton", "Talon",
    "Ring", "Helm", "Shield", "Probe", "Drive", "Matrix", "Crown",
]
ADVANCED_SUFFIXES = [
    "永恒", "湮灭", "星核", "超载", "共鸣", "觉醒", "创世", "灭世", "浩劫", "禁忌", "无限", "超维", "宿命", "涅槃",
]

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01"
    b"\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00"
    b"\x90wS\xde"
    b"\x00\x00\x00\nIDATx\x9cc``\x00\x00\x00\x04\x00\x01"
    b"\x0e\x9d\x0e\xc5"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def ensure_dirs():
    STATE_PATH.mkdir(parents=True, exist_ok=True)
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    FULL_DIR.mkdir(parents=True, exist_ok=True)


def load_state():
    ensure_dirs()
    if WAREHOUSE_FILE.exists():
        try:
            with WAREHOUSE_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = None
    else:
        data = None
    if not data:
        data = {
            "items": {},
            "garbage": {},
            "equipped": [],
            "supplies": {},
            "materials": {"星尘结晶": 0, "太古原石": 0, "空之宝石": 0, "虚空之镜": 0},
            "energy": 100,
            "last_roll_ts": None,
            "roll_history": [],
            "next_uid": 1,
        }
    normalize_state(state=data)
    return data


def normalize_state(state):
    max_uid = 0
    for storage_name in ["items", "garbage"]:
        storage = state.get(storage_name, {})
        for key, item in list(storage.items()):
            if not isinstance(item, dict):
                continue
            if item.get("uid") != key:
                item["uid"] = key
            if isinstance(key, str) and key.isdigit():
                max_uid = max(max_uid, int(key))
            elif isinstance(item.get("uid"), str) and item["uid"].isdigit():
                max_uid = max(max_uid, int(item["uid"]))
    next_uid = state.get("next_uid")
    if not isinstance(next_uid, int) or next_uid <= max_uid:
        state["next_uid"] = max(max_uid + 1, 1)
    normalized_equipped = []
    for entry in state.get("equipped", []):
        if isinstance(entry, str) and entry in state["items"]:
            normalized_equipped.append(entry)
            continue
        if isinstance(entry, int) or (isinstance(entry, str) and entry.isdigit()):
            code = int(entry)
            key, _ = find_item_entry(state["items"], code)
            if key:
                normalized_equipped.append(key)
    state["equipped"] = normalized_equipped


def refresh_next_uid(state):
    max_uid = 0
    for storage_name in ["items", "garbage"]:
        for key in state.get(storage_name, {}).keys():
            if isinstance(key, str) and key.isdigit():
                max_uid = max(max_uid, int(key))
    next_uid = state.get("next_uid", 1)
    if not isinstance(next_uid, int) or next_uid <= max_uid:
        state["next_uid"] = max_uid + 1


def save_state(state):
    refresh_next_uid(state)
    with WAREHOUSE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def parse_int(text):
    try:
        return int(re.sub(r"[^0-9]", "", text))
    except ValueError:
        return None


def get_rarity_for_code(code):
    for name, _, low, high, _ in RARITY_INFO:
        if low <= code <= high:
            return name
    return None


def choose_rarity(rnd):
    weights = [info[1] for info in RARITY_INFO]
    rarities = [info[0] for info in RARITY_INFO]
    return rnd.choices(rarities, weights)[0]


def get_range_for_rarity(rarity):
    for name, _, low, high, _ in RARITY_INFO:
        if name == rarity:
            return low, high
    raise ValueError(f"Unknown rarity: {rarity}")


def find_item_entry(storage, code=None, key=None):
    if key is not None:
        return key, storage.get(key)
    if code is not None:
        for key, item in storage.items():
            if item["id"] == code:
                return key, item
    return None, None


def uid_exists(state, uid):
    return uid in state.get("items", {}) or uid in state.get("garbage", {})


def generate_next_uid(state):
    next_uid = state.get("next_uid", 1)
    if not isinstance(next_uid, int) or next_uid <= 0:
        next_uid = 1
    while uid_exists(state, str(next_uid)):
        next_uid += 1
    uid = str(next_uid)
    state["next_uid"] = next_uid + 1
    return uid


def has_item(state, code):
    return any(item["id"] == code for item in state["items"].values()) or any(
        item["id"] == code for item in state["garbage"].values()
    )


def create_item(code, rarity):
    code = int(code)
    if rarity == "太初虚空" and code in SPECIAL_VOID:
        eng, cn = SPECIAL_VOID[code]
        return {
            "id": code,
            "rarity": rarity,
            "name": f"{eng} （{cn}）",
            "english": eng,
            "chinese": cn,
        }
    rnd = random.Random(code + RARITY_INDEX[rarity] * 10007)
    if rarity == "普通废料":
        if rnd.random() < 0.13:
            name = rnd.choice(COMMON_NAMES)
        else:
            prefix = rnd.choice(PREFIXES)
            base = rnd.choice(BASE_MODULES)
            name = f"{prefix}{base}"
    elif rarity == "魔法精制":
        prefix = rnd.choice(PREFIXES)
        modifier = rnd.choice(MODIFIERS)
        base = rnd.choice(BASE_MODULES)
        name = f"{prefix}{modifier}{base}"
    else:
        prefix = rnd.choice(PREFIXES)
        modifier = rnd.choice(MODIFIERS)
        base = rnd.choice(BASE_MODULES)
        name = f"{prefix}{modifier}{base}"
    return {
        "id": code,
        "rarity": rarity,
        "name": name,
    }


def upgrade_name(item):
    if item["rarity"] == "太初虚空":
        return item["name"]
    text = item["name"]
    if any(suffix in text for suffix in ADVANCED_SUFFIXES):
        return text
    rnd = random.Random(item["id"] + 6543)
    suffix = rnd.choice(ADVANCED_SUFFIXES)
    if "（" in text and "）" in text:
        return text
    return f"{text}·{suffix}"


def format_item(item, equipped=False):
    star = next((icon for name, _, _, _, icon in RARITY_INFO if name == item["rarity"]), "")
    equip_mark = " ⚔️" if equipped else ""
    return f"{item['id']}\t{item['name']}\t{star} {item['rarity']}{equip_mark}"


def item_locations(state, code):
    if any(item["id"] == code for item in state["items"].values()):
        return "items"
    if any(item["id"] == code for item in state["garbage"].values()):
        return "garbage"
    return None


def load_item_by_code(state, code):
    _, item = find_item_entry(state["items"], code)
    if item:
        return item
    _, item = find_item_entry(state["garbage"], code)
    return item


def find_equipped_key(state, code):
    for key in state["equipped"]:
        item = state["items"].get(key)
        if item and item["id"] == code:
            return key
    return None


def find_unequipped_item_key(state, code):
    for key, item in state["items"].items():
        if item["id"] == code and key not in state["equipped"]:
            return key
    return None


def maybe_restore_energy(state):
    now = time.time()
    last = state.get("last_roll_ts")
    if last is None:
        return
    if now - last >= 300 and state["energy"] < 100:
        state["energy"] = 100
        print("\n⚡ 5 分钟未进行任何 roll，能量已自动恢复至 100。\n")


def create_image_placeholder(path):
    try:
        with open(path, "wb") as handle:
            handle.write(PNG_BYTES)
    except OSError:
        pass


def generate_images_for_item(item):
    code = item["id"]
    name_part = item["name"].replace("/", "_").replace("\\", "_")
    filename = f"{code}_{item['rarity']}_{name_part}.png"
    icon = ICON_DIR / filename
    full = FULL_DIR / filename
    create_image_placeholder(icon)
    create_image_placeholder(full)
    return icon, full


def maybe_auto_generate_image(state, item):
    if item["rarity"] in ["太古沙丘", "太初虚空"]:
        icon, full = generate_images_for_item(item)
        print(f"📷 自动生成图片：{icon} 和 {full}")


def print_help():
    print("""
欢迎进入 Starborne 本地版
固定开场白：
  Starborne, the Transmute Artifact has chosen you.
  The universe is now at your command.

可用命令：
  roll / 单抽 / 掉落        单次拾荒（消耗 5 能量）
  roll10 / 十连 / 再来十连  十连拾荒（消耗 40 能量）
  货舱 / 查看货舱 / inventory  查看仓库装备
  当前装备 / 已装备 / gear    查看已穿戴装备
  穿 [编号]                  穿戴指定装备
  脱下 [编号] / 卸下 [编号]   卸下装备
  垃圾库                      查看垃圾库
  星舰能量状态               查看能量和补给
  萃取 [补给名称] / 使用 [补给名称]  使用补给恢复能量
  我的最强装备               显示稀有度最高装备
  删除装备 [编号]            删除指定装备
  清空货舱                   清空所有仓库装备（需确认）
  拆解 [编号]                拆解传奇及以上装备，获得材料
  升级 [编号]                使用材料升级装备到下一稀有度
  献祭 [编号]                太初虚空专属，破坏后刷新生成新太初
  画 [编号] / 图 [编号]      为指定装备生成占位图
  全部画图                    为仓库所有装备生成占位图
  重新画 [编号]              重新生成指定装备占位图
  检查作弊 / anti-cheat       查看最近 10 次 roll 随机种子记录
  help / 帮助                显示本说明
  exit / quit / 退出         退出游戏
""")


def show_inventory(state):
    if not state["items"]:
        print("仓库当前为空。")
        return
    print("📦 货舱 — 当前仓库装备：")
    sorted_items = sorted(
        state["items"].values(),
        key=lambda x: (RARITY_INDEX.get(x["rarity"], 0), x["id"]),
        reverse=True,
    )
    for item in sorted_items:
        equipped = item.get("uid") in state["equipped"]
        print(format_item(item, equipped))
    counts = {}
    for item in sorted_items:
        counts[item["rarity"]] = counts.get(item["rarity"], 0) + 1
    summary = " | ".join(f"{k}: {v}" for k, v in counts.items())
    print(f"\n共 {len(sorted_items)} 件 | {summary}")


def show_garbage(state):
    if not state["garbage"]:
        print("垃圾库当前为空。")
        return
    print("🗑️ 垃圾库：")
    for item in sorted(state["garbage"].values(), key=lambda x: x["id"]):
        print(format_item(item, False))
    print(f"\n共 {len(state['garbage'])} 件垃圾装备。")


def show_gear(state):
    if not state["equipped"]:
        print("当前没有穿戴任何装备。")
        return
    print("🛡️ 已装备：")
    for key in state["equipped"]:
        item = state["items"].get(key)
        if item:
            print(format_item(item, True))
    print(f"\n共穿戴 {len(state['equipped'])} 件。")


def show_energy(state):
    maybe_restore_energy(state)
    print(f"⚡ 当前能量：{state['energy']} / 100")
    print("补给：")
    if state["supplies"]:
        for name, count in state["supplies"].items():
            print(f"  {name} x{count}")
    else:
        print("  当前没有补给。")
    print("材料：")
    for name, count in state["materials"].items():
        print(f"  {name} x{count}")


def choose_supply():
    return random.choice(SUPPLIES)


def add_supply(state, supply_name, count=1):
    state["supplies"][supply_name] = state["supplies"].get(supply_name, 0) + count


def check_duplicate(state, code):
    return has_item(state, code)


def roll_once(state, rnd=None):
    maybe_restore_energy(state)
    if state["energy"] < 5:
        print("能量不足，当前能量不足 5，无法执行 roll。请使用补给或等待 5 分钟自动恢复。")
        return
    if rnd is None:
        rnd = random.Random()
    state["energy"] -= 5
    rarity = choose_rarity(rnd)
    low, high = get_range_for_rarity(rarity)
    code = rnd.randint(low, high)
    seed = rnd.getstate()
    now = time.time()
    state["last_roll_ts"] = now
    history_entry = {
        "ts": now,
        "code": code,
        "rarity": rarity,
        "energy": state["energy"],
        "seed": str(hash(seed)),
    }
    state["roll_history"].append(history_entry)
    if len(state["roll_history"]) > 10:
        state["roll_history"] = state["roll_history"][-10:]
    duplicate = check_duplicate(state, code)
    item = create_item(code, rarity)
    target = "items" if rarity in ["稀有古物", "传奇星核", "太古沙丘", "太初虚空"] else "garbage"
    storage_key = generate_next_uid(state)
    item["uid"] = storage_key
    state[target][storage_key] = item
    if duplicate:
        print(f"🎲 你又得到了编号 {code} 的复制品（当前稀有度：{rarity}）。")
    else:
        print(f"🎲 掉落结果：\n{format_item(item)}")
    if target == "items":
        print("已存入货舱。")
    else:
        print("已进入垃圾库。")
    maybe_auto_generate_image(state, item)
    if state["energy"] <= 30:
        supply, recover = choose_supply()
        add_supply(state, supply)
        print(f"低能量触发补给掉落：{supply}（恢复 {recover} 点），已送入补给仓库。")


def roll_ten(state):
    maybe_restore_energy(state)
    if state["energy"] < 40:
        print("当前能量不足以进行十连。请使用补给或等待 5 分钟自动恢复。")
        return
    print("开始十连掷骰子...")
    for i in range(10):
        roll_once(state)  # roll_once will deduct 5 each time and may restore images
    print("十连结束。")


def load_item_by_code(state, code):
    _, item = find_item_entry(state["items"], code)
    if item:
        return item
    _, item = find_item_entry(state["garbage"], code)
    return item


def equip_item(state, code):
    key, item = find_item_entry(state["items"], code)
    if not item:
        print("指定编号不在仓库中，无法穿戴。")
        return
    if key in state["equipped"]:
        next_key = find_unequipped_item_key(state, code)
        if not next_key:
            print("该装备已穿戴。")
            return
        key, item = next_key, state["items"][next_key]
    if len(state["equipped"]) >= 7:
        print("穿戴数量已达上限 7 件。请先卸下一件装备。")
        return
    state["equipped"].append(key)
    print(f"装备成功：{item['name']}")


def unequip_item(state, code):
    key = find_equipped_key(state, code)
    if not key:
        print("该编号当前未穿戴。")
        return
    state["equipped"].remove(key)
    item = state["items"].get(key)
    if item:
        print(f"已卸下：{item['name']}")
    else:
        print("已卸下装备。")


def use_supply(state, name):
    if name not in state["supplies"] or state["supplies"][name] <= 0:
        print("当前没有该补给。")
        return
    recover = next((recover for sup, recover in SUPPLIES if sup == name), None)
    if recover is None:
        print("未知补给，无法使用。")
        return
    state["supplies"][name] -= 1
    if state["supplies"][name] == 0:
        del state["supplies"][name]
    state["energy"] = min(100, state["energy"] + recover)
    print(f"使用补给 {name}，恢复 {recover} 能量。当前能量 {state['energy']} / 100。")


def show_best(state):
    if not state["items"]:
        print("仓库当前为空。")
        return
    sorted_items = sorted(
        state["items"].values(),
        key=lambda x: (RARITY_INDEX.get(x["rarity"], 0), x["id"]),
        reverse=True,
    )
    best = sorted_items[0]
    print("💎 当前最强装备：")
    print(format_item(best, best.get("uid") in state["equipped"]))


def clear_inventory(state):
    confirm = input("确认清空货舱？这将删除所有仓库装备。请输入 yes 确认：")
    if confirm.lower() == "yes":
        state["items"].clear()
        state["equipped"].clear()
        print("货舱已清空。")
    else:
        print("已取消清空。")


def delete_equipment(state, code):
    key, item = find_item_entry(state["items"], code)
    if key:
        state["items"].pop(key)
        if key in state["equipped"]:
            state["equipped"].remove(key)
        print("已删除指定装备。")
        return
    key, item = find_item_entry(state["garbage"], code)
    if key:
        state["garbage"].pop(key)
        print("已从垃圾库删除指定装备。")
        return
    print("未找到指定编号的装备。")


def dismantle(state, code):
    key, item = find_item_entry(state["items"], code)
    storage = "items"
    if not item:
        key, item = find_item_entry(state["garbage"], code)
        storage = "garbage"
    if not item:
        print("未找到指定编号的装备。")
        return
    if item["rarity"] not in ["传奇星核", "太古沙丘", "太初虚空"]:
        print("只有传奇及以上装备可以拆解。")
        return
    if storage == "items" and key:
        state["items"].pop(key)
    if storage == "garbage" and key:
        state["garbage"].pop(key)
    if key in state["equipped"]:
        state["equipped"].remove(key)
    if item["rarity"] == "传奇星核":
        state["materials"]["星尘结晶"] += 1
        print("拆解成功，获得 星尘结晶 x1。")
    elif item["rarity"] == "太古沙丘":
        state["materials"]["太古原石"] += 1
        print("拆解成功，获得 太古原石 x1。")
    else:
        choice = random.choice(["空之宝石", "虚空之镜"])
        state["materials"][choice] += 1
        print(f"拆解成功，获得 {choice} x1。")


def upgrade_item(state, code):
    key, item = find_item_entry(state["items"], code)
    if not item:
        print("指定编号的装备必须在仓库中才能升级。")
        return
    current = item["rarity"]
    if current == "太初虚空":
        print("太初虚空已经是最高稀有度，无法升级。")
        return
    next_rarity = RARITY_ORDER[RARITY_INDEX[current] + 1]
    if current in ["普通废料", "魔法精制", "稀有古物"]:
        required = "星尘结晶"
    elif current == "传奇星核":
        required = "太古原石"
    elif current == "太古沙丘":
        if state["materials"].get("空之宝石", 0) > 0:
            required = "空之宝石"
        elif state["materials"].get("虚空之镜", 0) > 0:
            required = "虚空之镜"
        else:
            required = None
    else:
        required = None
    if not required or state["materials"].get(required, 0) <= 0:
        need_text = "空之宝石 或 虚空之镜" if current == "太古沙丘" else required
        print(f"升级到 {next_rarity} 需要 {need_text} x1，当前材料不足。")
        return
    state["materials"][required] -= 1
    if state["materials"][required] == 0:
        del state["materials"][required]
    item["rarity"] = next_rarity
    print(f"升级成功：{item['name']}，已提升至 {next_rarity}。")


def sacrifice(state, code):
    key, item = find_item_entry(state["items"], code)
    if not item:
        print("指定编号必须在仓库中。")
        return
    if item["rarity"] != "太初虚空":
        print("只有太初虚空可以献祭。")
        return
    state["items"].pop(key)
    if key in state["equipped"]:
        state["equipped"].remove(key)
    low, high = get_range_for_rarity("太初虚空")
    candidate = None
    attempts = 0
    while attempts < 100:
        new_code = random.randint(low, high)
        if not has_item(state, new_code):
            candidate = new_code
            break
        attempts += 1
    if candidate is None:
        print("当前太初编号已满，无法生成新太初虚空。")
        return
    new_item = create_item(candidate, "太初虚空")
    state["items"][str(candidate)] = new_item
    print(f"献祭完成，摧毁 {code}，生成新太初虚空：{format_item(new_item)}")
    maybe_auto_generate_image(state, new_item)


def draw_images(state, code):
    item = load_item_by_code(state, code)
    if not item:
        print("未找到指定编号的装备。")
        return
    icon, full = generate_images_for_item(item)
    print(f"已生成占位图：{icon} 和 {full}")


def draw_all_images(state):
    if not state["items"] and not state["garbage"]:
        print("当前无装备可生成图片。")
        return
    for item in list(state["items"].values()) + list(state["garbage"].values()):
        generate_images_for_item(item)
    print("已为当前所有装备生成占位图。")


def show_anti_cheat(state):
    if not state["roll_history"]:
        print("暂无 roll 记录。")
        return
    print("最近 10 次 roll 随机记录：")
    for entry in state["roll_history"]:
        ts = datetime.fromtimestamp(entry["ts"]).strftime("%Y-%m-%d %H:%M:%S")
        print(f"  {ts} | 编号 {entry['code']} | 稀有度 {entry['rarity']} | 能量 {entry['energy']} | 种子 {entry['seed']}")


def repair_materials(state, name):
    if name == "星尘结晶":
        needed = 2
        if state["materials"].get(name, 0) < needed:
            print("材料不足，无法合成太古原石。")
            return
        state["materials"][name] -= needed
        state["materials"]["太古原石"] += 1
        print("合成成功：太古原石 x1。")
    elif name == "太古原石":
        needed = 2
        if state["materials"].get(name, 0) < needed:
            print("材料不足，无法合成太初材料。")
            return
        state["materials"][name] -= needed
        choice = random.choice(["空之宝石", "虚空之镜"])
        state["materials"][choice] += 1
        print(f"合成成功：{choice} x1。")
    else:
        print("无法合成该材料。")


def command_loop():
    state = load_state()
    print("Starborne, the Transmute Artifact has chosen you.")
    print("The universe is now at your command.")
    print_help()
    while True:
        try:
            line = input("\n> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n退出游戏。")
            save_state(state)
            break
        if not line:
            continue
        cmd = line.strip()
        cmd_lower = cmd.lower()
        if cmd_lower in ["exit", "quit", "退出"]:
            save_state(state)
            print("已保存进度，退出游戏。")
            break
        if cmd_lower in ["help", "帮助"]:
            print_help()
        elif cmd_lower in ["roll", "单抽", "掉落"]:
            roll_once(state)
        elif cmd_lower in ["roll10", "十连", "再来十连"]:
            roll_ten(state)
        elif cmd_lower in ["货舱", "查看货舱", "inventory"]:
            show_inventory(state)
        elif cmd_lower in ["已装备", "当前装备", "gear"]:
            show_gear(state)
        elif cmd_lower.startswith("穿 "):
            code = parse_int(cmd)
            if code is None:
                print("请输入有效编号。")
            else:
                equip_item(state, code)
        elif cmd_lower.startswith("脱下 ") or cmd_lower.startswith("卸下 "):
            code = parse_int(cmd)
            if code is None:
                print("请输入有效编号。")
            else:
                unequip_item(state, code)
        elif cmd_lower in ["垃圾库"]:
            show_garbage(state)
        elif cmd_lower in ["星舰能量状态"]:
            show_energy(state)
        elif cmd_lower.startswith("萃取 ") or cmd_lower.startswith("使用 "):
            name = cmd.split(" ", 1)[1].strip()
            if not name:
                print("请输入补给名称。")
            else:
                use_supply(state, name)
        elif cmd_lower in ["我的最强装备"]:
            show_best(state)
        elif cmd_lower.startswith("删除装备 "):
            code = parse_int(cmd)
            if code is None:
                print("请输入有效编号。")
            else:
                delete_equipment(state, code)
        elif cmd_lower in ["清空货舱"]:
            clear_inventory(state)
        elif cmd_lower.startswith("拆解 "):
            code = parse_int(cmd)
            if code is None:
                print("请输入有效编号。")
            else:
                dismantle(state, code)
        elif cmd_lower.startswith("升级 "):
            code = parse_int(cmd)
            if code is None:
                print("请输入有效编号。")
            else:
                upgrade_item(state, code)
        elif cmd_lower.startswith("献祭 "):
            code = parse_int(cmd)
            if code is None:
                print("请输入有效编号。")
            else:
                sacrifice(state, code)
        elif cmd_lower.startswith("画 ") or cmd_lower.startswith("图 "):
            code = parse_int(cmd)
            if code is None:
                print("请输入有效编号。")
            else:
                draw_images(state, code)
        elif cmd_lower == "全部画图":
            draw_all_images(state)
        elif cmd_lower.startswith("重新画 "):
            code = parse_int(cmd)
            if code is None:
                print("请输入有效编号。")
            else:
                draw_images(state, code)
        elif cmd_lower in ["检查作弊", "anti-cheat"]:
            show_anti_cheat(state)
        elif cmd_lower.startswith("合成 "):
            name = cmd.split(" ", 1)[1].strip()
            if not name:
                print("请输入要合成的材料名称，例如：合成 星尘结晶")
            else:
                repair_materials(state, name)
        else:
            print("未知命令。输入 help 或 帮助 查看可用命令。")
        save_state(state)


if __name__ == "__main__":
    command_loop()
