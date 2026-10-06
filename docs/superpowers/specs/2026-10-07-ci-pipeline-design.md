# CI pipeline — dizayn

**Sana:** 2026-10-07
**Holat:** tasdiqlangan dizayn, spec ko'rib chiqilmoqda
**Manba:** `keyingi_qadamlar.md`, F bo'limi — "CI pipeline: pytest + ruff + mypy"

## Maqsad

Har bir `main` ga push va har bir pull request uchun GitHub Actions avtomatik
ravishda `ruff`, `mypy` va unit testlarni ishga tushirsin. Xato bo'lsa build
qizil bo'ladi.

**Muvaffaqiyat mezoni:** yangi workflow GitHub'da yashil o'tadi. U ishlatadigan
buyruqlar lokal Python 3.11 muhitda ham bir xil natija beradi: ruff xatosiz,
mypy xatosiz, pytest `241 passed, 13 skipped`.

## Cheklovlar

- **Production'ga ta'sir yo'q.** CI hech qanday bazaga ulanmaydi.
  `DATABASE_URL` va `TEST_DATABASE_URL` berilmaydi, shuning uchun integration
  testlar o'zi skip bo'ladi. Secret'lar ishlatilmaydi.
- **Qamrov:** faqat unit testlar va lint. PostgreSQL integration job bu
  vazifaga kirmaydi (foydalanuvchi qarori).
- **Python 3.11:** Render'dagi production versiyasi (`render.yaml`:
  `PYTHON_VERSION=3.11.9`) va `pyproject.toml` dagi `requires-python >=3.11`
  bilan mos.

## Yondashuv

Bitta job, qadamlar ketma-ket: `ruff check .` → `mypy bot` → `pytest -q`.

Rad etilgan variantlar:
- *Matritsa 3.11 + 3.14:* production faqat 3.11 da ishlaydi, shuning uchun
  ikkinchi versiya ortiqcha (YAGNI).
- *Uchta parallel job:* testlar ~5 soniyada tugaydi. Dependency'larni uch
  marta o'rnatish vaqtni tejash o'rniga oshiradi.

## O'zgarishlar

### 1. `.github/workflows/ci.yml` (yangi)

- Trigger: `push` (`main` branch) va `pull_request`.
- `runs-on: ubuntu-latest`, `actions/setup-python` (3.11, pip cache
  `requirements-dev.txt` bo'yicha).
- `pip install -r requirements-dev.txt`.
- Qadamlar: `ruff check .`, `mypy bot`, `pytest -q`.
- `permissions: contents: read`. Workflow faqat kodni o'qiydi.

### 2. `requirements-dev.txt` (yangi)

```
-r requirements.txt
pytest~=8.0
pytest-asyncio~=0.23
ruff~=0.5
mypy~=1.10
```

Versiyalar `pyproject.toml` dagi `[project.optional-dependencies].dev` bilan
bir xil. `pip install ".[dev]"` ishlatilmaydi, chunki `pyproject.toml` da
`openpyxl` yo'q va build-system sozlanmagan.

### 3. `bot/presentation/handlers/debt_creation.py`: 2 ta mypy xatosi

`FSMContext.update_data(data: Mapping | None = None, **kwargs)`. Kalit
o'zgaruvchi bo'lsa, mypy `**{key: value}` qiymati `data` parametriga tushib
qolishi mumkin deb hisoblaydi. Runtime'da xato yo'q, chunki kalit hech qachon
`"data"` bo'lmaydi. Tuzatish: lug'at `data` argumenti sifatida beriladi.

```python
await state.update_data({list_key: items})                  # cb_edit_delete
await state.update_data({_EDIT_TARGETS[prefix][1]: index})  # cb_edit_redo
```

Xulq o'zgarmaydi. Boshqa qatorlarga tegilmaydi.

## Xatolarni boshqarish

Biror qadam yiqilsa job to'xtaydi va build qizil bo'ladi. mypy majburiy
tekshiruv: `continue-on-error` ishlatilmaydi.

## Tekshiruv

1. Lokal toza Python 3.11 venv'da `requirements-dev.txt` o'rnatiladi, keyin
   uchala buyruq workflow tartibida ishga tushiriladi.
2. Workflow YAML sintaksisi tekshiriladi.
3. GitHub'da haqiqiy run: trigger faqat `main` ga push va `pull_request` da
   ishlaydi. Shuning uchun `main` ga tegmasdan tekshirishning yo'li branch'ni
   push qilib, **draft PR** ochish. Bu faqat foydalanuvchi ruxsat bergandan
   keyin qilinadi (repo public, tashqariga chiqadigan amal). Draft PR Render
   deploy'ni ishga tushirmaydi.

## Qamrovdan tashqari

- PostgreSQL integration job (keyingi bosqich, `keyingi_qadamlar.md` B).
- `pyproject.toml` ga `openpyxl` qo'shish. Bu alohida nomuvofiqlik, bu
  yerda faqat qayd etiladi.
- Lokal `.venv/bin/mypy` shebang muammosi (eski `qarzly/.venv` yo'li). Bu
  lokal muhit muammosi, repo'ga tegishli emas.
