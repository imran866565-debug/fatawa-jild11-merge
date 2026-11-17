#!/usr/bin/env python3
"""Merge Jild 11 tashreeh chunks into jild-11.json.

Re-runnable: reads every jild-11-chunk-*.json listed in the manifest,
merges in chunk order, validates (unique ids, page coverage vs manifest,
no empty jawab), writes jild-11.json, and updates the manifest statuses.

Manifest structure: entry "02" is a "split-halves" placeholder
(no file on disk) — its halves 02a/02b are separate entries with their
own files. Placeholders are skipped.

SPECIAL CASES (coordinator instructions, verified on disk by the parent):
11 same-id pairs are ONE mas'ala split across chunks and must be
COMBINED into a single item, NOT renamed by the duplicate-id rule.
After combining all 11, the merged file has 394 items (405 - 11)
covering 626 unique pages. Combine rules per id (first = earlier chunk,
second = later chunk, ordered by min page):
  masala 8:   sawal from first; jawab = first + second concatenated.
  masala 16:  SPECIAL — chunk 03's sawal is already a FULL restatement
              of the whole question (verified against source pp. 191-192).
              Take pages [191, 192], sawal = second's, jawab = second's;
              DISCARD first's sawal, do NOT concatenate the two sawals.
  masala 46:  sawal from first; jawab = first + second concatenated.
  masala 135: sawal from first; jawab from second.
  masala 201: sawal from first; jawab = first + second concatenated.
  masala 255: sawal from first; jawab from second.
  masala 287: sawal from first; jawab from second.
  masala 325: sawal from first; jawab = first + second concatenated.
  masala 342: sawal from first; jawab = first + second concatenated.
  masala 394: sawal from first; jawab = first + second concatenated.
  masala 437: sawal from first; jawab = first + second concatenated.
For every combined item: pages = union of both halves' pages,
start_page = min, notes = both files' notes combined.

Distinct-id duplicates (different masail sharing a printed number) are
NOT combined — they already have distinct ids and stay separate:
306 (jild11-masala-306 + jild11-p523), 347 (jild11-masala-347 +
jild11-p620), 422 (jild11-masala-421-422 + jild11-p686), 104
(jild11-masala-104 + jild11-p275).

Duplicate-id rule (Jild 4 precedent) still applies to any OTHER
duplicate: earliest keeps the plain id, later ones get "-p<startpage>".
"""
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))

# id -> (sawal source, jawab source); 'first' = earlier chunk, 'second' = later.
COMBINES = {
    'jild11-masala-8':   ('first', 'concat'),
    'jild11-masala-16':  ('second', 'second'),   # SPECIAL: discard first's sawal
    'jild11-masala-46':  ('first', 'concat'),
    'jild11-masala-135': ('first', 'second'),
    'jild11-masala-201': ('first', 'concat'),
    'jild11-masala-255': ('first', 'second'),
    'jild11-masala-287': ('first', 'second'),
    'jild11-masala-325': ('first', 'concat'),
    'jild11-masala-342': ('first', 'concat'),
    'jild11-masala-394': ('first', 'concat'),
    'jild11-masala-437': ('first', 'concat'),
}


def combine_pair(item_id, first, second):
    sawal_rule, jawab_rule = COMBINES[item_id]
    sawal = (first if sawal_rule == 'first' else second).get('tashreeh_sawal', '')
    if jawab_rule == 'concat':
        jawab = (first.get('tashreeh_jawab', '') or '') + (second.get('tashreeh_jawab', '') or '')
    else:
        jawab = (second.get('tashreeh_jawab', '') or '')
    combined = {
        'id': item_id,
        'title': first.get('title') or second.get('title', ''),
        'volume_id': 54,
        'pages': sorted(set(first['pages']) | set(second['pages'])),
        'start_page': min(first['pages']),
        'tashreeh_sawal': sawal,
        'tashreeh_jawab': jawab,
        'notes': list(first.get('notes') or []) + list(second.get('notes') or []),
    }
    return combined


def main():
    manifest = json.load(open(os.path.join(BASE, 'chunks-manifest-jild11.json')))
    all_items = []
    merged_chunks = []
    for entry in manifest['chunks']:
        nn = entry['chunk']
        if entry.get('status') == 'split-halves':
            print(f'chunk {nn}: split-halves placeholder — halves are separate entries, skipping')
            continue
        path = os.path.join(BASE, entry['file'])
        if not os.path.exists(path):
            print(f'chunk {nn}: not yet written')
            continue
        try:
            d = json.load(open(path, encoding='utf-8'))
        except json.JSONDecodeError as e:
            # File may still be streaming from its translator; skip it
            # for now instead of crashing the whole merge.
            print(f'chunk {nn}: not valid JSON yet ({e}) — skipping for now')
            continue
        items = d['masail']
        # Normalize: some translators omit start_page; derive it from pages.
        for it in items:
            if 'start_page' not in it:
                assert it.get('pages'), f'chunk {nn} item {it.get("id")} has no pages'
                it['start_page'] = it['pages'][0]
                print(f'chunk {nn}: derived start_page={it["start_page"]} for {it["id"]}')
            assert it['start_page'] == min(it['pages']), \
                f'chunk {nn} item {it["id"]}: start_page != first page'
        all_items.extend(items)
        merged_chunks.append(nn)
        entry['status'] = 'merged'
        print(f'chunk {nn}: {len(items)} items merged')
    print(f'items before combines: {len(all_items)}')
    # COMBINE the 11 same-id pairs (one mas'ala split across chunks).
    for item_id, (sawal_rule, jawab_rule) in COMBINES.items():
        pair = [it for it in all_items if it['id'] == item_id]
        assert len(pair) == 2, f'expected exactly 2 {item_id} items, found {len(pair)}'
        pair.sort(key=lambda it: min(it['pages']))
        first, second = pair
        if item_id == 'jild11-masala-16':
            assert second.get('tashreeh_sawal'), 'masala-16: second half must carry the full sawal'
            assert not first.get('tashreeh_jawab'), 'masala-16: first half jawab must be empty (partner holds it)'
        combined = combine_pair(item_id, first, second)
        assert combined['tashreeh_jawab'], f'{item_id}: combined jawab is empty!'
        all_items = [it for it in all_items if it['id'] != item_id]
        all_items.append(combined)
        print(f'COMBINED {item_id}: pages {combined["pages"]}, '
              f'sawal {len(combined["tashreeh_sawal"])} chars, '
              f'jawab {len(combined["tashreeh_jawab"])} chars, notes {len(combined["notes"])}')
    # de-duplicate any OTHER ids: earliest keeps plain id, later ones get -p<startpage>
    seen = {}
    for it in all_items:
        if it['id'] in seen:
            new_id = f"{it['id']}-p{it['start_page']}"
            print(f'DUPLICATE ID {it["id"]} (start {it["start_page"]}) -> renamed {new_id}')
            it['id'] = new_id
        seen[it['id']] = True
    ids = [it['id'] for it in all_items]
    assert len(ids) == len(set(ids)), f'STILL DUPLICATE IDS: {[i for i in ids if ids.count(i) > 1]}'
    empty = [it['id'] for it in all_items if not it.get('tashreeh_jawab')]
    assert not empty, f'EMPTY JAWAB: {empty}'
    pages = set()
    for it in all_items:
        pages.update(it['pages'])
    expected = set()
    for entry in manifest['chunks']:
        if entry['chunk'] in merged_chunks:
            expected.update(range(entry['start_page'], entry['end_page'] + 1))
            expected.difference_update(entry['missing_pages'])
    missing_covered = expected - pages
    extra = pages - expected
    print(f'total items: {len(all_items)} | pages covered: {len(pages)} | expected: {len(expected)}')
    print(f'uncovered expected pages: {sorted(missing_covered)}')
    print(f'extra pages (outside merged chunks): {sorted(extra)}')
    assert not missing_covered, 'pages missing from merged chunks!'
    assert not extra, 'pages outside merged chunks!'
    assert len(all_items) == 394, f'expected 394 items after combines, got {len(all_items)}'
    assert len(pages) == 626, f'expected 626 pages, got {len(pages)}'
    # sort by start_page for the final file
    all_items.sort(key=lambda it: it['start_page'])
    with open(os.path.join(BASE, 'jild-11.json'), 'w', encoding='utf-8') as f:
        json.dump({'masail': all_items}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(BASE, 'chunks-manifest-jild11.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f'WROTE jild-11.json: {len(all_items)} items, {len(pages)} pages, chunks merged: {merged_chunks}')


if __name__ == '__main__':
    main()
