#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_index.py
--------------
Διαβάζει το structure.txt και παράγει index.html για την ιστοσελίδα Ανταίος.

Χρήση:
    python build_index.py [structure.txt] [template.html] [output.html]

Προεπιλογές:
    structure.txt  →  είσοδος (το markdown αρχείο δομής)
    index.html     →  template ΚΑΙ έξοδος (διαβάζεται και αντικαθίσταται)
                       Εναλλακτικά: αν υπάρχει template.html, αυτό χρησιμοποιείται
                       ως βάση και το αποτέλεσμα πηγαίνει στο index.html.

Μορφή structure.txt
--------------------
<about> Τίτλος </about>
  Παράγραφοι κειμένου. Κενή γραμμή → <br><br>.
  Σύνδεσμοι εντός κειμένου: [κείμενο](url)

# Τίτλος          →  κύρια ενότητα μενού
## Τίτλος         →  υποενότητα mega-menu

Γραμμές εντός ενότητας:
  [Κείμενο](url)  →  ενεργός σύνδεσμος
  [Κείμενο]()     →  χωρίς σύνδεσμο (υπό κατασκευή), αποδίδεται με link: "#"
"""

import re
import sys
from pathlib import Path


# ─────────────────────────────────────────────────────────────
# 1. PARSER: structure.txt  →  Python data
# ─────────────────────────────────────────────────────────────

# Regex για markdown σύνδεσμο: [κείμενο](url)  ή  [κείμενο]()
RE_MD_LINK = re.compile(r'\[([^\]]+)\]\(([^)]*)\)')


def md_links_to_html(text: str) -> str:
    """Μετατρέπει [κείμενο](url) → <a href="url" ...>κείμενο</a>.
    Αν το url είναι κενό, δεν παράγεται <a> — απλό κείμενο."""
    def replace(m):
        label, url = m.group(1), m.group(2).strip()
        if url:
            return f'<a href="{url}" target="_blank" class="text-link">{label}</a>'
        return label  # κενό url → μόνο κείμενο
    return RE_MD_LINK.sub(replace, text)


def parse_line_as_item(line: str) -> dict | None:
    """
    Αναλύει μια γραμμή ενότητας.
    Επιστρέφει {'text': ..., 'link': ...} ή None αν η γραμμή είναι κενή.
      [Κείμενο](url)  → link = url
      [Κείμενο]()     → link = None  (υπό κατασκευή)
    """
    stripped = line.strip()
    if not stripped:
        return None

    m = RE_MD_LINK.match(stripped)
    if m:
        label = m.group(1).strip()
        url   = m.group(2).strip()
        return {'text': label, 'link': url if url else None}

    # Απλό κείμενο χωρίς markdown (backward compat)
    return {'text': stripped, 'link': None}


def parse_structure(path: str) -> dict:
    """
    Επιστρέφει:
    {
        'about': {'title': str, 'html': str},
        'menus': [
            {
                'id':       'menu2',
                'label':    str,
                'title':    str,
                'type':     'simple' | 'mega',
                'items':    [{'text': str, 'link': str|None}, ...],   # simple
                'sections': [{'title': str,                           # mega
                               'items': [{'text': str, 'link': str|None}]}]
            }, ...
        ]
    }
    """
    text  = Path(path).read_text(encoding='utf-8')
    lines = text.splitlines()

    about       = {'title': 'Περί', 'html': ''}
    menus       = []
    about_lines = []
    cur_menu    = None
    cur_section = None
    state       = None   # 'about' | 'section' | 'subsection'

    def flush_about():
        raw        = '\n'.join(about_lines).strip()
        paragraphs = re.split(r'\n{2,}', raw)
        parts      = []
        for p in paragraphs:
            p = p.strip()
            if p:
                parts.append(md_links_to_html(p))
        about['html'] = '\n<br><br>\n'.join(parts)

    def finalize_menu(menu):
        if menu and menu['type'] == 'mega' and not menu.get('sections'):
            menu['type'] = 'simple'
            menu.setdefault('items', [])

    for line in lines:

        # ── <about> tag ───────────────────────────────────────────
        m_about = re.match(r'<about>\s*(.*?)\s*</about>', line.strip())
        if m_about:
            about['title'] = m_about.group(1) or 'Περί'
            state = 'about'
            continue

        # ── # Κύρια ενότητα ───────────────────────────────────────
        m_h1 = re.match(r'^#\s+(.+)$', line)
        if m_h1:
            if state == 'about':
                flush_about()
            finalize_menu(cur_menu)
            title    = m_h1.group(1).strip()
            cur_menu = {
                'id':       f'menu{len(menus) + 2}',
                'label':    title,
                'title':    title,
                'type':     'simple',
                'items':    [],
                'sections': [],
            }
            menus.append(cur_menu)
            cur_section = None
            state       = 'section'
            continue

        # ── ## Υποενότητα ─────────────────────────────────────────
        m_h2 = re.match(r'^##\s+(.+)$', line)
        if m_h2 and cur_menu:
            title       = m_h2.group(1).strip()
            cur_menu['type'] = 'mega'
            cur_section = {'title': title, 'items': []}
            cur_menu['sections'].append(cur_section)
            state = 'subsection'
            continue

        # ── Γραμμές εντός ενότητας ────────────────────────────────
        if state in ('section', 'subsection'):
            item = parse_line_as_item(line)
            if item:
                target = cur_section['items'] if cur_section else cur_menu['items']
                target.append(item)
            continue

        # ── Κείμενο about ─────────────────────────────────────────
        if state == 'about':
            about_lines.append(line)

    # Flush τελευταίων
    if state == 'about':
        flush_about()
    finalize_menu(cur_menu)

    return {'about': about, 'menus': menus}


# ─────────────────────────────────────────────────────────────
# 2. BUILDER: data  →  JS / HTML strings
# ─────────────────────────────────────────────────────────────

def item_to_js(item: dict, indent: str) -> str:
    """Μετατρέπει ένα item σε JS object literal.
       link=None  →  link: "#"
       link=''    →  link: "#"  (κενό url = υπό κατασκευή)
       link=url   →  link: "url"
    """
    text = item['text'].replace('\\', '\\\\').replace('"', '\\"')
    link = item['link'] or '#'
    link = link.replace('\\', '\\\\').replace('"', '\\"')
    return f'{indent}{{ text: "{text}", link: "{link}" }}'


def build_submenu_content(data: dict) -> str:
    about = data['about']
    menus = data['menus']
    lines = ['const submenuContent = {']

    # menu1 = About
    # Τα backticks στο about html δεν χρειάζονται escape
    # (δεν περιέχουν backtick από τη φύση τους)
    about_html = about['html']
    lines += [
        '\t\t\tmenu1: {',
        '\t\t\t\ttitle: "About",',
        '\t\t\t\titems: [',
        '\t\t\t\t\t{',
        '\t\t\t\t\t\ttype: "text",',
        f'\t\t\t\t\t\tcontent: `\n{about_html}\n\t\t\t\t\t\t`',
        '\t\t\t\t\t}',
        '\t\t\t\t]',
        '\t\t\t},',
    ]

    for menu in menus:
        mid   = menu['id']
        title = menu['title'].replace('"', '\\"')
        lines.append(f'\t\t\t{mid}: {{')
        lines.append(f'\t\t\t\ttitle: "{title}",')

        if menu['type'] == 'mega':
            lines.append('\t\t\t\ttype: "mega",')
            lines.append('\t\t\t\tsections: [')
            for sec in menu['sections']:
                stitle = sec['title'].replace('"', '\\"')
                lines += [
                    '\t\t\t\t\t{',
                    f'\t\t\t\t\t\ttitle: "{stitle}",',
                    '\t\t\t\t\t\titems: [',
                ]
                for item in sec['items']:
                    lines.append(item_to_js(item, '\t\t\t\t\t\t\t') + ',')
                lines += ['\t\t\t\t\t\t]', '\t\t\t\t\t},']
            lines.append('\t\t\t\t]')
        else:
            lines.append('\t\t\t\titems: [')
            for item in menu['items']:
                lines.append(item_to_js(item, '\t\t\t\t\t') + ',')
            lines.append('\t\t\t\t]')

        lines.append('\t\t\t},')

    lines.append('\t\t};')
    return '\n'.join(lines)


def build_menu_labels_html(data: dict) -> str:
    lines = ['\t\t<div class="menu-label" data-for-menu="menu1">Περί...</div>']
    for menu in data['menus']:
        lines.append(
            f'\t\t<div class="menu-label" data-for-menu="{menu["id"]}">'
            f'{menu["label"]}</div>'
        )
    return '\n'.join(lines)


def build_menu_meta_js(data: dict) -> str:
    lines = ['const menuMeta = [']
    lines.append("\t\t\t\t{ id: 'menu1', label: 'Περί...' },")
    for menu in data['menus']:
        label = menu['label'].replace("'", "\\'")
        lines.append(f"\t\t\t\t{{ id: '{menu['id']}', label: '{label}' }},")
    lines.append('\t\t\t];')
    return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────
# 3. INJECTOR: αντικαθιστά τμήματα του template HTML
# ─────────────────────────────────────────────────────────────

def inject_into_html(template_path: str, output_path: str, data: dict):
    html = Path(template_path).read_text(encoding='utf-8')

    # submenuContent
    html = re.sub(
        r'const submenuContent\s*=\s*\{.*?\};',
        build_submenu_content(data),
        html, flags=re.DOTALL
    )

    # menuMeta
    html = re.sub(
        r'const menuMeta\s*=\s*\[.*?\];',
        build_menu_meta_js(data),
        html, flags=re.DOTALL
    )

    # menu-labels div — αντικαθιστά ολόκληρο το block μετρώντας nested <div>
    def replace_menu_labels(html, new_inner):
        m = re.search(r'<div id="menu-labels"[^>]*>', html)
        if not m:
            return html
        start = m.start()
        pos   = m.end()   # αμέσως μετά το opening tag
        depth = 1         # έχουμε ήδη ανοίξει 1
        while pos < len(html) and depth > 0:
            if re.match(r'<div[\s>]', html[pos:]):
                depth += 1
                pos   += 4
            elif html[pos:pos+6] == '</div>':
                depth -= 1
                if depth == 0:
                    end = pos + 6
                    break
                pos += 6
            else:
                pos += 1
        replacement = (
            '<div id="menu-labels" class="menu-labels">\n'
            + new_inner + '\n\t</div>'
        )
        return html[:start] + replacement + html[end:]

    html = replace_menu_labels(html, build_menu_labels_html(data))

    Path(output_path).write_text(html, encoding='utf-8')
    total = len(data['menus']) + 1
    print(f'✓  {output_path}  ({total} menus: About + {len(data["menus"])})')


# ─────────────────────────────────────────────────────────────
# 4. MAIN
# ─────────────────────────────────────────────────────────────

def main():
    # Βάση: ο φάκελος του ίδιου του script, όχι ο τρέχων φάκελος.
    # Έτσι δουλεύει ανεξάρτητα από το terminal working directory.
    base = Path(__file__).parent

    args      = sys.argv[1:]
    structure = Path(args[0]) if len(args) > 0 else base / 'structure.txt'

    # Template: ψάχνει template.html, αλλιώς χρησιμοποιεί index.html
    if len(args) > 1:
        template = Path(args[1])
    elif (base / 'template.html').exists():
        template = base / 'template.html'
    else:
        template = base / 'index.html'

    output    = Path(args[2]) if len(args) > 2 else base / 'index.html'

    print(f'structure → {structure}')
    print(f'template  → {template}')
    print(f'output    → {output}')
    print()

    data = parse_structure(structure)

    # Σύνοψη
    print(f'About: "{data["about"]["title"]}"')
    for m in data['menus']:
        if m['type'] == 'mega':
            secs = ', '.join(s['title'] for s in m['sections'])
            print(f'  [{m["id"]}] {m["title"]}  (mega → {secs})')
        else:
            links    = [i for i in m['items'] if i['link']]
            no_links = [i for i in m['items'] if not i['link']]
            print(f'  [{m["id"]}] {m["title"]}  '
                  f'({len(links)} link(s), {len(no_links)} υπό κατασκευή)')
    print()

    inject_into_html(template, output, data)


if __name__ == '__main__':
    main()