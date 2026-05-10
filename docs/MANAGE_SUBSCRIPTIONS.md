# UP涓昏闃呯鐞嗘寚鍗?

## 馃摵 鏂规硶涓€锛氫氦浜掑紡绠＄悊宸ュ叿锛堟帹鑽愶級

浣跨敤鎴戜负浣犲垱寤虹殑绠＄悊鑴氭湰锛屽彲浠ヨ交鏉炬坊鍔犮€佹煡鐪嬨€佺紪杈戝拰鍒犻櫎UP涓昏闃呫€?

### 鍚姩绠＄悊宸ュ叿

```bash
cd /Users/aniss/Code/bili-flow
uv run python manage_subscriptions.py
```

### 鍔熻兘璇存槑

```
1锔忊儯  鏌ョ湅鎵€鏈塙P涓昏闃?
    鏄剧ず褰撳墠鏁版嵁搴撲腑鐨勬墍鏈夎闃匲P涓诲強鍏剁姸鎬?

2锔忊儯  娣诲姞鍗曚釜UP涓?
    閫愪釜杈撳叆UP涓籌D (mid)銆佸悕瀛椼€佸娉ㄧ瓑淇℃伅
    绀轰緥:
    - mid: 1988098633
    - 鍚嶅瓧: 鏉庢瘬浣?
    - 澶囨敞: 绉戞妧UP涓伙紙鍙€夛級

3锔忊儯  鎵归噺娣诲姞UP涓?
    涓€娆℃€ф坊鍔犲涓猆P涓伙紝鏍煎紡涓? mid|鍚嶅瓧|澶囨敞
    绀轰緥:
    1988098633|鏉庢瘬浣硘绉戞妧UP涓?
    399658881|缃楃繑璇存硶寰媩娉曞緥璁茶В
    锛堟寜 Ctrl+D 缁撴潫杈撳叆锛?

4锔忊儯  缂栬緫UP涓讳俊鎭?
    淇敼UP涓荤殑鍚嶅瓧鎴栧娉?

5锔忊儯  鍚敤/绂佺敤UP涓?
    鏆傛椂鍋滄鎴栨仮澶嶅鏌愪釜UP涓荤殑妫€娴?

6锔忊儯  鍒犻櫎UP涓?
    鍒犻櫎涓嶅啀闇€瑕佸叧娉ㄧ殑UP涓昏闃?

0锔忊儯  閫€鍑?
    閫€鍑虹▼搴?
```

---

## 馃悕 鏂规硶浜岋細Python 涓€琛屽懡浠?

### 娣诲姞鍗曚釜UP涓?

```bash
uv run python -c "
from app.models.database import get_db, Subscription

db = get_db()
sub = Subscription(mid='1988098633', name='鏉庢瘬浣?, notes='绉戞妧UP涓?)
db.add(sub)
db.commit()
print('鉁?鎴愬姛娣诲姞UP涓? 鏉庢瘬浣?)
"
```

### 鎵归噺娣诲姞澶氫釜UP涓?

```bash
uv run python -c "
from app.models.database import get_db, Subscription

db = get_db()

# UP涓讳俊鎭垪琛?
uppers = [
    {'mid': '1988098633', 'name': '鏉庢瘬浣?, 'notes': '绉戞妧UP涓?},
    {'mid': '399658881', 'name': '缃楃繑璇存硶寰?, 'notes': '娉曞緥璁茶В'},
    {'mid': '2070143629', 'name': '娌圭鎼繍宸?, 'notes': '鑻辨枃瀛楀箷鎼繍'},
]

for upper in uppers:
    # 妫€鏌ユ槸鍚﹀凡瀛樺湪
    existing = db.query(Subscription).filter_by(mid=upper['mid']).first()
    if existing:
        print(f\"鈴笍  璺宠繃: {upper['name']} (宸插瓨鍦?\")
        continue
    
    sub = Subscription(
        mid=upper['mid'],
        name=upper['name'],
        notes=upper['notes']
    )
    db.add(sub)
    print(f\"鉁?娣诲姞: {upper['name']}\")

db.commit()
print('鉁?鍏ㄩ儴瀹屾垚')
"
```

---

## 馃搵 鏂规硶涓夛細閰嶇疆鏂囦欢瀵煎叆

棣栧厛锛屽垱寤轰竴涓?`subscriptions.txt` 鏂囦欢锛屾牸寮忎负 `mid|鍚嶅瓧|澶囨敞`锛?

```txt
1988098633|鏉庢瘬浣硘绉戞妧UP涓?
399658881|缃楃繑璇存硶寰媩娉曞緥璁茶В
2070143629|娌圭鎼繍宸鑻辨枃瀛楀箷鎼繍
156160448|鏈变竴鏃︾殑鏋嚗鐢熸椿|骞介粯UP涓?
```

鐒跺悗杩愯瀵煎叆鑴氭湰锛?

```bash
uv run python -c "
from app.models.database import get_db, Subscription

db = get_db()

with open('subscriptions.txt', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        parts = line.split('|')
        if len(parts) < 2:
            continue
        
        mid = parts[0].strip()
        name = parts[1].strip()
        notes = parts[2].strip() if len(parts) > 2 else None
        
        # 妫€鏌ユ槸鍚﹀凡瀛樺湪
        existing = db.query(Subscription).filter_by(mid=mid).first()
        if existing:
            print(f'鈴笍  璺宠繃: {name}')
            continue
        
        sub = Subscription(mid=mid, name=name, notes=notes)
        db.add(sub)
        print(f'鉁?娣诲姞: {name}')

db.commit()
print('鉁?瀵煎叆瀹屾垚')
"
```

---

## 馃搳 濡備綍鑾峰彇UP涓荤殑 MID

### 鏂瑰紡1锛氫粠缃戝潃鑾峰彇
- 璁块棶UP涓讳富椤碉紝URL鏍煎紡: `https://space.bilibili.com/{MID}`
- 澶嶅埗 `{MID}` 閮ㄥ垎鍗冲彲

### 鏂瑰紡2锛欱绔橝PI鏌ヨ
```bash
curl "https://api.bilibili.com/x/web-interface/search/type?search_type=bili_user&keyword=鏉庢瘬浣? | grep -o '"mid":[0-9]*' | head -1
```

### 鏂瑰紡3锛氬父瑙乁P涓荤殑MID

| UP涓?| MID | 绫诲埆 |
|------|------|------|
| 鏉庢瘬浣?| 1988098633 | 绉戞妧/璇勬祴 |
| 缃楃繑璇存硶寰?| 399658881 | 娉曞緥璁茶В |
| 娌圭鎼繍宸?| 2070143629 | 鑻辨枃鎼繍 |
| 鏈变竴鏃︾殑鏋嚗鐢熸椿 | 156160448 | 濞变箰/骞介粯 |
| 鍗婃辰鐩存爲鐮旂┒鎵€ | 1395169867 | 鐣墽/鍒嗘瀽 |
| 楂樺北瀹氬＋ | 159041871 | 鍔ㄦ极璇勬祴 |
| 鐙煎彅 | 337338227 | 娓告垙 |

---

## 鉁?楠岃瘉璁㈤槄鏄惁娣诲姞鎴愬姛

娣诲姞鍚庯紝鍙互閫氳繃浠ヤ笅鏂瑰紡楠岃瘉锛?

```bash
# 鏌ョ湅鎵€鏈夎闃?
uv run python -c "
from app.models.database import get_db, Subscription

db = get_db()
subs = db.query(Subscription).filter_by(is_active=True).all()

print('\\n=== 娲昏穬UP涓昏闃?===\\n')
for sub in subs:
    print(f'馃摵 {sub.name} (MID: {sub.mid})')
    if sub.notes:
        print(f'   馃摑 {sub.notes}')
print(f'\\n馃搳 鎬昏: {len(subs)} 涓?)
"
```

---

## 馃殌 鍚姩绯荤粺寮€濮嬫娴?

娣诲姞UP涓诲悗锛屽惎鍔ㄤ富绋嬪簭锛?

```bash
uv run python main.py
```

绯荤粺灏嗭細
1. 姣?10 鍒嗛挓妫€娴嬩竴娆℃墍鏈塙P涓荤殑鏂拌棰?
2. 姣?5 鍒嗛挓妫€娴嬩竴娆℃墍鏈塙P涓荤殑鏂板姩鎬?
3. 鑷姩澶勭悊鍙戠幇鐨勬柊鍐呭

鏌ョ湅瀹炴椂鏃ュ織锛?
```bash
tail -f logs/bili.log
```

---

## 馃挕 甯歌闂

**Q: 濡備綍鏆傚仠鏌愪釜UP涓荤殑妫€娴嬶紵**
A: 杩愯绠＄悊宸ュ叿锛岄€夋嫨 "5锔忊儯 鍚敤/绂佺敤UP涓?锛岀鐢ㄥ嵆鍙€?

**Q: 濡備綍淇敼UP涓荤殑淇℃伅锛?*
A: 杩愯绠＄悊宸ュ叿锛岄€夋嫨 "4锔忊儯 缂栬緫UP涓讳俊鎭?銆?

**Q: 娣诲姞鍚庡涔呬細寮€濮嬪鐞嗭紵**
A: 鏈€澶氱瓑寰?5-10 鍒嗛挓锛堝彇鍐充簬妫€娴嬪懆鏈燂級銆?

**Q: 濡備綍瀵煎嚭宸叉坊鍔犵殑UP涓诲垪琛紵**
A: 杩愯绠＄悊宸ュ叿锛岄€夋嫨 "1锔忊儯 鏌ョ湅鎵€鏈塙P涓?锛屾垨鐢ㄤ互涓嬪懡浠わ細
```bash
uv run python -c "
from app.models.database import get_db, Subscription
db = get_db()
for sub in db.query(Subscription).all():
    print(f'{sub.mid}|{sub.name}|{sub.notes or \"\"}')
"
```

---

## 馃攧 鏁版嵁搴撳瓧娈佃鏄?

| 瀛楁 | 璇存槑 | 绀轰緥 |
|------|------|------|
| `mid` | UP涓籙ID锛堝敮涓€锛?| 1988098633 |
| `name` | UP涓绘樀绉?| 鏉庢瘬浣?|
| `notes` | 澶囨敞锛堝彲閫夛級 | 绉戞妧UP涓?|
| `is_active` | 鏄惁婵€娲?| true |
| `last_check_time` | 鏈€鍚庢娴嬫椂闂?| 2026-03-26 16:30 |
| `last_video_bvid` | 鏈€鍚庢娴嬬殑瑙嗛ID | BVxxxxxx |
| `last_dynamic_id` | 鏈€鍚庢娴嬬殑鍔ㄦ€両D | 123456789 |

---

**鐜板湪灏卞紑濮嬫坊鍔犱綘鐨勯涓猆P涓诲惂锛?* 馃帀

