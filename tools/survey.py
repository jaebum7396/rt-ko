"""Survey Owlcat Strings JSON + enGB.json: field shapes, speakers, categories, word counts (RTKO-8)."""
import json, os, re, sys, collections

ROOT = sys.argv[1] if len(sys.argv) > 1 else '/data2/rt-ko/template/Strings'
EN = sys.argv[2] if len(sys.argv) > 2 else '/data2/rt-ko/game/WH40KRT_Data/StreamingAssets/Localization/enGB.json'
OUT = sys.argv[3] if len(sys.argv) > 3 else '/data2/rt-ko/survey.json'

en = {k: (v.get('Text') or '') for k, v in json.load(open(EN, encoding='utf-8-sig'))['strings'].items()}
top, lang_keys, trait_names, speakers, cats = (collections.Counter() for _ in range(5))
cat_words = collections.Counter()
key_path, missing_en, placeholders = {}, 0, 0
for dp, _, fs in os.walk(ROOT):
    for f in fs:
        if not f.endswith('.json'):
            continue
        p = os.path.join(dp, f)
        try:
            d = json.load(open(p, encoding='utf-8-sig'))
        except Exception:
            continue
        top.update(d.keys())
        k = d.get('key')
        rel = os.path.relpath(p, ROOT)
        key_path[k] = rel
        parts = rel.split(os.sep)
        cat = '/'.join(parts[2:4]) if parts[:2] == ['Mechanics', 'Blueprints'] else '/'.join(parts[:2])
        spk = ''
        for L in d.get('languages', []):
            lang_keys.update(L.keys())
            for t in L.get('traits', []) or []:
                trait_names[t.get('trait')] += 1
                if t.get('speaker'):
                    spk = spk or t['speaker']
        for t in d.get('string_traits', []) or []:
            trait_names['string:' + str(t.get('trait'))] += 1
        if spk:
            speakers[spk] += 1
        txt = en.get(k)
        if txt is None:
            missing_en += 1
            continue
        if txt.strip() in ('', 'Placeholder', 'draft'):
            placeholders += 1
            continue
        cats[cat] += 1
        cat_words[cat] += len(txt.split())
print('top-level keys', top.most_common())
print('language entry keys', lang_keys.most_common())
print('traits', trait_names.most_common(20))
print('files', len(key_path), ' not in enGB', missing_en, ' placeholder/empty', placeholders,
      ' enGB keys without file', len(set(en) - set(key_path)))
print('speakers (distinct)', len(speakers), ' lines with speaker', sum(speakers.values()))
print('top speakers', speakers.most_common(25))
print('category  strings  words')
for c, n in sorted(cats.items(), key=lambda x: -cat_words[x[0]]):
    print(f'  {c:45s} {n:6d} {cat_words[c]:9d}')
print('total words', sum(cat_words.values()))
json.dump({'key_path': key_path, 'speakers': speakers, 'cat_words': cat_words, 'cats': cats}, open(OUT, 'w'))
