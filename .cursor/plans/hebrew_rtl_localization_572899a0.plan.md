---
name: Hebrew RTL Localization
overview: Localize the user-facing Admin Dashboard and WhatsApp customer messages to Hebrew (RTL). Hebrew-only UI; backend HTTP error strings stay English (mapped to generic Hebrew toasts on the frontend). DB schema and enum keys are unchanged.
todos:
  - id: html_rtl_font
    content: Set <html dir="rtl" lang="he">, swap font to Heebo, flip physical Tailwind classes (search icon, toasts, dropdowns) in frontend/index.html
    status: pending
  - id: html_copy
    content: Translate all hard-coded English copy in frontend/index.html (header, table headers, modals, buttons, placeholders) per the proposed mapping
    status: pending
  - id: js_labels
    content: Translate STATUS, REASONS, STATS_META, filter tabs, modal titles, and row Edit button labels in frontend/app.js
    status: pending
  - id: js_dynamic
    content: Translate dynamic empty/filtered/loading messages, success/error toasts, validation messages, and API key flow strings in frontend/app.js
    status: pending
  - id: js_errors_dates
    content: Add status-based Hebrew mapping for backend errors in apiFetch and switch fmtDate locale to he-IL
    status: pending
  - id: whatsapp_templates
    content: Translate STATUS_MESSAGES, _GENERIC_STATUS_COPY, NON_TEXT_REPLY, INVALID_PLATE_REPLY, format_vehicle_status, format_not_found in app/whatsapp/formatting.py
    status: pending
  - id: verify
    content: Run pytest and do a manual visual + WhatsApp dry-run check
    status: pending
isProject: false
---

## Scope and decisions

- **UI language:** Hebrew-only. No language toggle. (per user)
- **Server errors:** `app/routers/*`, `app/dependencies.py`, `app/schemas/vehicle.py` keep English `detail` text. Frontend maps known HTTP errors to generic Hebrew toasts. (per user)
- **Database:** No migration. Status/Reason enum **values** (`ticket_opened`, `annual`, etc.) stay English keys; only display labels are translated. WhatsApp templates written directly in Hebrew strings.
- **Frontend stack reality:** No build step, no npm, no i18n library, single `index.html` + `app.js`, Tailwind via CDN. We do NOT introduce a build pipeline. We add a tiny inline `i18n` dictionary in `app.js` plus translate inline HTML, and switch the document to RTL.

## Files touched

- `frontend/index.html` — RTL, font, all hard-coded English copy.
- `frontend/app.js` — `STATUS`/`REASONS`/`STATS_META` labels, dynamic strings, validation, toasts, date locale, generic server-error toast mapping.
- `app/whatsapp/formatting.py` — all six status sentences, generic copy, NON_TEXT_REPLY, INVALID_PLATE_REPLY, `format_vehicle_status`, `format_not_found`.
- `tests/` — no changes expected; tests reference `STATUS_MESSAGES` by enum, not literals (verified).

---

## Step 1 — Document shell, RTL, font ([frontend/index.html](frontend/index.html))

- Set `<html lang="he" dir="rtl">`.
- Replace the Inter Google Font import with a Hebrew-first font. Recommended: **Heebo** (matches Inter's geometric feel and supports Hebrew + Latin):

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;600;700&display=swap" rel="stylesheet">
```

  Then `body { font-family: 'Heebo', sans-serif; }` in the inline `<style>`.
- Audit physical Tailwind utilities that need flipping for RTL (Tailwind CDN doesn't ship RTL logical utilities, so we just swap classes since UI is Hebrew-only):
  - Search input icon: `left-3` → `right-3`; input `pl-10` → `pr-10`.
  - Toast container `bottom-4 right-4` → `bottom-4 left-4` (toasts on the natural visual end in RTL).
  - Any dropdown/menu using `left-0` → `right-0` (and vice-versa).
  - `text-left` → `text-right` where appropriate (table cells stay default, which inherits RTL).
  - `space-x-*` / `divide-x` will visually mirror correctly under `dir="rtl"`; review only if anything looks off.

## Step 2 — Translate inline HTML copy ([frontend/index.html](frontend/index.html))

Apply this mapping (English → Hebrew):

- Title `Garage Manager — Admin` → `מערכת ניהול מוסך`
- Header brand `Garage Manager` → `ניהול המוסך`
- Subtitle `Admin Dashboard` → `לוח בקרה`
- Header button `Add Vehicle` → `הוספת רכב`
- Search placeholder `Search plate or customer…` → `חיפוש לפי לוחית רישוי או לקוח…`
- Table headers:
  - `Plate` → `לוחית רישוי`
  - `Customer` → `שם הלקוח`
  - `Phone` → `טלפון`
  - `Status` → `סטטוס`
  - `Reason` → `סיבת טיפול`
  - `Added` → `נוסף בתאריך`
- Empty state default: `No vehicles yet` → `עדיין אין רכבים`; `Click "Add Vehicle" to get started.` → `לחצו על "הוספת רכב" כדי להתחיל.`
- Loading: `Loading vehicles…` → `טוען רכבים…`
- Vehicle modal:
  - Default title `Add Vehicle` → `הוספת רכב`
  - `License Plate *` → `לוחית רישוי *`; placeholder `e.g. 1234567` → `למשל 1234567`
  - `Customer Name *` → `שם הלקוח *`; placeholder `First Last` → `שם פרטי שם משפחה`
  - `Phone Number *` → `מספר טלפון *`; placeholder `0501234567` (unchanged)
  - `Status` → `סטטוס`; option labels (mirror `STATUS` table below)
  - `Reason` → `סיבת טיפול`; option labels (mirror `REASONS` table below)
  - `Delete Vehicle` → `מחק רכב`; `Cancel` → `ביטול`; submit `Add Vehicle` → `הוסף רכב`
- API key modal:
  - `Admin API Key Required` → `נדרש מפתח גישה`
  - Body copy → `הזינו את מפתח ה-API של הניהול כדי לפתוח את לוח הבקרה. המפתח נשמר רק עבור חלון הדפדפן הנוכחי.`
  - `API Key` → `מפתח API`; placeholder `••••••••••••` (unchanged)
  - `Cancel` → `ביטול`; `Unlock` → `כניסה`

## Step 3 — Translate dynamic strings ([frontend/app.js](frontend/app.js))

- **`STATUS` labels:**
  - `ticket_opened`: `כרטיס נפתח`
  - `mechanics`: `אצל המוסכניק`
  - `in_test`: `בנסיעת מבחן`
  - `washing`: `בשטיפה`
  - `ready_for_payment`: `ממתין לתשלום`
  - `ready`: `מוכן לאיסוף`

- **`REASONS`:**
  - `annual`: `טיפול שנתי`
  - `accident`: `תאונה`
  - `bodywork`: `פחחות`
  - `diagnostics`: `אבחון`

- **`STATS_META`:**
  - `Total Vehicles` → `סה"כ רכבים`
  - Per-status labels reuse the `STATUS` mapping above.

- **Filter tabs:** first tab `'All'` → `'הכל'`. The remaining tabs read from `STATUS[k].label` and update automatically.

- **Empty / filtered states:**
  - `No vehicles match "X"` → `לא נמצאו רכבים התואמים ל-"X"`
  - `No vehicles with status "X"` → `אין רכבים בסטטוס "X"`
  - `No vehicles yet` → `עדיין אין רכבים`
  - `Try adjusting your search or filter.` → `נסו לעדכן את החיפוש או הסינון.`
  - `Click "Add Vehicle" to get started.` → `לחצו על "הוספת רכב" כדי להתחיל.`

- **Row actions / modal buttons:**
  - `Edit` → `עריכה`
  - `Edit Vehicle` (modal title) → `עריכת רכב`
  - `Save Changes` → `שמירת שינויים`
  - `Saving…` → `שומר…`; `Adding…` → `מוסיף…`; `Deleting…` → `מוחק…`
  - Delete confirm `Delete vehicle "X"?\nThis cannot be undone.` → `למחוק את הרכב "X"?\nלא ניתן לבטל פעולה זו.`

- **Toasts (success):**
  - `` Status → ${label} `` → `` סטטוס עודכן ל-${label} ``
  - `Vehicle updated` → `הרכב עודכן`
  - `Vehicle added` → `הרכב נוסף`
  - `Vehicle deleted` → `הרכב נמחק`

- **API key flow:**
  - `That key was rejected. Please try again.` → `המפתח נדחה. נסו שוב.`
  - `API key required` → `נדרש מפתח API`
  - `Please enter a key.` → `יש להזין מפתח.`

- **Frontend validation messages:**
  - `License plate is required.` → `יש להזין לוחית רישוי.`
  - `License plate must be exactly 7 or 8 digits.` → `לוחית הרישוי חייבת להכיל 7 או 8 ספרות בלבד.`
  - `Customer name is required.` → `יש להזין שם לקוח.`
  - Two-words rule → `שם הלקוח חייב להיות שתי מילים בלבד (אותיות בעברית או באנגלית) המופרדות ברווח אחד.`
  - `Phone number is required.` → `יש להזין מספר טלפון.`
  - Phone rule → `מספר הטלפון חייב להכיל 10 ספרות, להתחיל ב-"05", והספרה השלישית חייבת להיות 0/2/3/4/5/8.`
  - `Please select a valid reason.` → `יש לבחור סיבת טיפול תקינה.`

- **Generic server-error mapping** (since backend stays English, translate at the boundary). In the `apiFetch` helper, when a non-OK response is received, replace the raw English `detail` with a Hebrew message based on HTTP status:
  - `401`/`403` → `נדרשת התחברות מחדש.` (and re-open API-key modal as today)
  - `404` → `הרכב לא נמצא.`
  - `409` → `רכב עם לוחית הרישוי הזו כבר קיים במערכת.`
  - `422` → `הנתונים שהוזנו אינם תקינים.`
  - any other → `אירעה שגיאה. נסו שוב.`

- **Date formatting:** in `fmtDate` change `'en-GB'` → `'he-IL'`. Keep options `{ day: '2-digit', month: 'short', year: '2-digit' }` (Hebrew month abbreviations render correctly).

## Step 4 — WhatsApp templates ([app/whatsapp/formatting.py](app/whatsapp/formatting.py))

Replace literals (enum keys unchanged):

- `STATUS_MESSAGES`:
  - `ticket_opened`: `פתחנו עבורכם כרטיס שירות לרכב. נעדכן אתכם בהתקדמות.`
  - `mechanics`: `המוסכניקים שלנו מטפלים ברכב כעת.`
  - `in_test`: `הרכב נמצא בנסיעת מבחן לאימות התיקון.`
  - `washing`: `הרכב עובר שטיפה — השלב האחרון לפני האיסוף.`
  - `ready_for_payment`: `הרכב מוכן. נא להסדיר את התשלום כדי שנוכל למסור אותו.`
  - `ready`: `בשורה טובה! הרכב מוכן לאיסוף.`
- `_GENERIC_STATUS_COPY` → `הרכב נמצא כעת בטיפולנו.`
- `NON_TEXT_REPLY` → `נא לשלוח את לוחית הרישוי כהודעת טקסט.`
- `INVALID_PLATE_REPLY` → `הלוחית שנשלחה אינה תקינה. נא לשלוח 7 או 8 ספרות, למשל 1234567.`
- `format_vehicle_status` template:

```python
return (
    f"שלום {vehicle.customer_name},\n"
    f"סטטוס לוחית {vehicle.license_plate}: {status_copy(vehicle.status)}\n"
    "— המוסך"
)
```

- `format_not_found` →

```python
return (
    f"לא הצלחנו לאתר רכב עם לוחית {plate}. "
    "נא לבדוק שוב או להתקשר אלינו."
)
```

No changes to `app/whatsapp/client.py`, `service.py`, `schemas.py`, or routers. Green API accepts UTF-8 message bodies; the existing JSON encoding handles Hebrew automatically.

## Step 5 — Out of scope (intentional, per decisions)

- `app/main.py` OpenAPI title/description, `app/dependencies.py` API-key error, `app/routers/*` 404/409/401 details, and `app/schemas/vehicle.py` Pydantic messages stay English. They're surfaced to the admin UI through the generic Hebrew status-based mapping in Step 3, and remain useful for logs / direct API consumers.
- No DB migration. Enum value strings (`ticket_opened`, `mechanics`, …, `annual`, …) remain English identifiers — they are keys, not labels.
- No new dependency, no build tool. Tailwind RTL plugin is unnecessary because it's a Hebrew-only UI; we simply set `dir="rtl"` and swap the few physical-direction classes listed in Step 1.

## Step 6 — Verification checklist

- Visual pass on `frontend/index.html` open in a browser: `dir="rtl"`, font renders Hebrew, all labels translated, search icon on the right, toasts on the bottom-left.
- Run pytest: `tests/test_whatsapp.py` and `tests/test_vehicles.py` should pass unchanged (verified that WhatsApp tests reference `STATUS_MESSAGES` by symbol, not by English literal; vehicle tests don't assert on response `detail` Hebrew text).
- Manual WhatsApp dry run: send a plate via the webhook with each status and confirm the Hebrew reply text matches the table above.