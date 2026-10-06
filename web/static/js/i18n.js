/**
 * QARZ DAFTAR — Mini App tillari: o'zbek (lotin), o'zbek (kirill), rus.
 *
 * Matnlar kodda lotin o'zbekchada `t('...')` bilan yoziladi:
 * - kirill varianti `toCyrillic` bilan avtomatik hosil qilinadi
 *   (bot/i18n/translit.py bilan bir xil qoidalar — testda solishtiriladi);
 * - ruscha tarjima `window.I18N_RU` lug'atidan olinadi (i18n-ru.js).
 * Statik HTML matnlari `translateDom()` bilan bir marta o'giriladi.
 */

const I18N_LANGUAGES = {
    uz: "O'zbekcha (lotin)",
    uz_cyrl: 'Ўзбекча (кирилл)',
    ru: 'Русский',
};
const LANG_STORAGE_KEY = 'qarz-lang';

let currentLang = (() => {
    try {
        const saved = localStorage.getItem(LANG_STORAGE_KEY);
        return saved in I18N_LANGUAGES ? saved : 'uz';
    } catch (e) {
        return 'uz';
    }
})();

function setLanguage(lang) {
    currentLang = lang in I18N_LANGUAGES ? lang : 'uz';
    try {
        localStorage.setItem(LANG_STORAGE_KEY, currentLang);
    } catch (e) {}
    document.documentElement.lang = currentLang === 'ru' ? 'ru' : 'uz';
}

// --- Lotin → kirill ---------------------------------------------------------

const _KEEP_WORDS = [
    'Mini App', 'Web UI', 'Excel', 'Exchange', 'exchange', 'Telegram ID',
    'DD.MM.YYYY', 'UZS', 'USD', 'EFB', 'Ah', 'OK', 'ID', 'A → Z', 'Z → A',
];
const _PROTECTED_RE = new RegExp(
    '(<[^>]*>|&[a-zA-Z#0-9]+;|\\{[^}]*\\}|/[a-z_]+|'
    + [..._KEEP_WORDS].sort((a, b) => b.length - a.length)
        .map(w => '\\b' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b').join('|')
    + ')'
);
const _APOSTROPHES = "'’ʼ‘ʻ`";
const _VOWELS = new Set('aeiouAEIOUаеиоуўэАЕИОУЎЭ');
const _DIGRAPHS = { sh: 'ш', ch: 'ч', yo: 'ё', yu: 'ю', ya: 'я', ye: 'е' };
const _SINGLE = {
    a: 'а', b: 'б', c: 'ц', d: 'д', f: 'ф', g: 'г', h: 'ҳ', i: 'и', j: 'ж', k: 'к',
    l: 'л', m: 'м', n: 'н', o: 'о', p: 'п', q: 'қ', r: 'р', s: 'с', t: 'т', u: 'у',
    v: 'в', w: 'в', x: 'х', y: 'й', z: 'з',
};
const _isAlpha = ch => !!ch && ch.toLowerCase() !== ch.toUpperCase();
const _isUpper = ch => !!ch && ch !== ch.toLowerCase();
const _case = (src, cyr) => (_isUpper(src[0]) ? cyr.toUpperCase() : cyr);

function _translitChunk(text) {
    let out = '';
    let i = 0;
    while (i < text.length) {
        const ch = text[i];
        const low = ch.toLowerCase();
        const nxt = text[i + 1] || '';
        const after = text[i + 2] || '';

        // o' → ў, g' → ғ (faqat keyin harf kelsa yoki so'z oxirida)
        if ((low === 'o' || low === 'g') && nxt && _APOSTROPHES.includes(nxt)
            && (_isAlpha(after) || !after || !after.trim())) {
            out += _case(ch, low === 'o' ? 'ў' : 'ғ');
            i += 2;
            continue;
        }
        const pair = (ch + nxt).toLowerCase();
        // "yo'q" — bu "yo" emas, "y" + "o'"
        if (pair in _DIGRAPHS && !(pair === 'yo' && after && _APOSTROPHES.includes(after))) {
            out += _case(ch, _DIGRAPHS[pair]);
            i += 2;
            continue;
        }
        if (low === 'e') {
            const prev = text[i - 1] || '';
            const initial = !_isAlpha(prev) || _VOWELS.has(prev);
            out += _case(ch, initial ? 'э' : 'е');
        } else if (low in _SINGLE) {
            out += _case(ch, _SINGLE[low]);
        } else if (_APOSTROPHES.includes(ch)) {
            const prev = text[i - 1] || '';
            // So'z ichidagi tutuq belgisi → ъ, qo'shtirnoq vazifasidagisi qoladi
            out += _isAlpha(prev) && _isAlpha(nxt) ? 'ъ' : ch;
        } else {
            out += ch;
        }
        i += 1;
    }
    return out;
}

function toCyrillic(text) {
    return text.split(_PROTECTED_RE).map((p, i) => (i % 2 ? p : _translitChunk(p))).join('');
}

// --- Tarjima ---------------------------------------------------------------

function translate(text, lang = currentLang) {
    if (lang === 'ru') return (window.I18N_RU || {})[text] ?? text;
    if (lang === 'uz_cyrl') return toCyrillic(text);
    return text;
}

/** Matnni joriy tilga o'giradi; `vars` — `{nom}` o'rniga qo'yiladigan qiymatlar. */
function t(text, vars) {
    const result = translate(text);
    if (!vars) return result;
    return result.replace(/\{(\w+)\}/g, (m, key) => (key in vars ? String(vars[key]) : m));
}

/** Matnni tarjima qilinadigan deb belgilaydi (keyin `t()` bilan o'giriladi). */
function N_(text) {
    return text;
}

/** Statik HTML matnlari va placeholder/aria-label/title atributlarini o'giradi. */
function translateDom(root = document.body) {
    if (currentLang === 'uz') return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        acceptNode: node => (node.parentElement?.closest('script, style, [data-no-i18n]')
            ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(node => {
        const text = node.nodeValue.trim();
        if (!/[a-zA-Z]/.test(text)) return;
        node.nodeValue = node.nodeValue.replace(text, translate(text));
    });
    root.querySelectorAll('[placeholder], [aria-label], [title]').forEach(el => {
        if (el.closest('[data-no-i18n]')) return;
        ['placeholder', 'aria-label', 'title'].forEach(attr => {
            const value = el.getAttribute(attr);
            if (value && /[a-zA-Z]/.test(value)) el.setAttribute(attr, translate(value));
        });
    });
}
