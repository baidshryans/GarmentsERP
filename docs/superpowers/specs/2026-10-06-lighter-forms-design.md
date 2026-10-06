# Lighter entry forms (piece 3)

Date: 2026-10-06. Status: owner chose "Fold under More options" and "Start blank, must choose"; built on `master` directly.

## Problem

Entry forms show every field at once (the party form has 25; three are needed every time), preselect the first supplier / customer / fabricator silently, and still use ERP jargon the menu has already dropped.

## Rules for every form

No model, URL-conf or migration change. Field `name`s posted to the server stay the same, so views and services keep working. Labels change in templates and form classes only (never `verbose_name`, which would need a migration). Nothing about validation that protects postings is loosened.

### 1. More options

- Each form shows what is needed every time. The rest sits in one closed section on the same form: `<details class="more">` with the summary "More options" followed, in muted text, by what is inside (e.g. "contact, GST, selling terms").
- It opens by itself when any field inside holds a value that differs from its default, or has an error, so nothing a user entered is ever hidden.
- One shared look (tokens only) and one shared way to build it, for both hand-written forms and Django form pages. A section with a more specific job uses a specific name instead: "Transport details", "Tax (GST / TDS)".
- Keyboard and screen-reader friendly: native `<details>`; the summary is reachable by Tab; fields inside are not focusable while closed (native behaviour).
- On "new" forms of the small masters, "Active" is not shown (it defaults to on); it appears on edit.

### 2. Party must be chosen

Supplier, customer and fabricator selects start with "Choose…" and the form is not saved until one is picked: the server refuses with a plain message naming the field ("Choose the supplier.") and returns the form with everything typed kept. The field stays prefilled when the page is opened from another document or a Next button that already knows the party (`?vendor=`, `?party=`, a purchase order, a challan step's fabricator). Location selects keep their sensible default.

### 3. Conditional fields

Fields that only apply to one choice appear only for that choice (as quick billing already does for GST), with the server ignoring the others exactly as it does today:

- Supplier bill: one "GST" choice is visible (default "No tax"); the template, by-hand amounts and "input credit" appear only for the modes that use them.
- Labour rate: only the fields of the chosen rate type show. Types are named in plain words: "Per piece", "Per piece plus extras", "Different rate per size", "Fixed amount per lot" (stored values unchanged).
- Money paid / Money received: the Bill, Reference and Due columns take no space unless a chosen ledger keeps bills.

### 4. What stays visible, what folds

| Form | Visible | Folded (section name) |
| --- | --- | --- |
| Party | Firm name; "This party is a": Customer, Supplier, Fabricator; Mobile; GSTIN when the company is GST-registered | More options: contact person, other phones, email, PAN, GSTIN otherwise, category, price list, discount, credit limit and days, payment terms, agent, transporter, destination, TDS section, "also an agent / transporter", Active |
| Style | Style no, Name, Product, Colours, Sizes, Default route, HSN code when GST-registered | More options: description, MRP, image, HSN otherwise, Archived |
| Material | Code, Name, Kind, Unit | More options: composition, GSM, width, Active (edit only) |
| Other small masters | all (they have 3–4 fields); Active on edit only | none |
| BOM | lines; wastage % stays | More options: version note; per-size quantities stay as columns |
| Purchase order | Supplier, Date, lines | More options: expected by, notes |
| Goods received | Supplier, Receive into, Date, lines | More options: supplier's challan no. and date, notes |
| Supplier bill | Supplier's bill no., Bill date, lines, GST choice | Tax (GST / TDS): TDS, and the GST detail fields per rule 3; More options: booking date, notes |
| Return to supplier | Supplier, Date, Reason, lines | Tax (GST): GST on the return, input credit |
| Production order | Date, Due by, lines | More options: for (stock / made to order), order reference, notes |
| Send to fabricator | Lot, Step, Fabricator, Date, Expected by, bundles | More options: notes; "Kind" is not asked when the page is opened for normal job work (rework arrives by its own link) but stays reachable |
| Receive from fabricator | Date, bundles and counts, trims when present | More options: receive into (prefilled) |
| Labour bill | Fabricator, rows, Bill date | More options: TDS, notes |
| Labour rate | Fabricator, Process, Rate type, From, the chosen type's rate fields | More options: rework rate |
| Sale order | Customer, Date, Due by, Type, styles | More options: notes |
| Packing | Pack from, Date, cartons | Transport details: transporter, LR / docket no., LR date, vehicle no., notes |
| Quick billing | as today | More options: notes |
| Return from customer | as today | none |
| Money paid / received | Date, Paid from / Received in, rows | More options: notes |
| Journal, Contra | as today | none (accountant screens) |

### 5. Words

On screen (titles, labels, buttons, messages), never in printed documents, document numbers, model names or stored values:

| Was | Now |
| --- | --- |
| Vendor, Is vendor | Supplier |
| Is customer / Is fabricator / Is agent / Is transporter | Customer / Fabricator / Agent / Transporter, under "This party is a" |
| New GRN, Edit GRN, GRN lines, GRN rate | Goods received, Received goods to bill, Received rate |
| Purchase invoice, Vendor invoice no. | Supplier bill, Supplier's bill no. |
| Debit note (purchase side) | Return to supplier |
| New challan, Save challan | Send to fabricator, Save |
| Remarks, Narration, Notes | Notes |
| Tds section, Hsn, Mrp, Gsm, Width cm, Is active, Is archived | TDS section, HSN code, MRP, GSM, Width (cm), Active, Archived |
| Deadlines | "Expected by" for goods coming in (purchase order, back from fabricator); "Due by" for what we promised (sale order, production order) |

Service error messages that reach the screen follow the same words. Trade terms the owner's staff use stay searchable through Ctrl+K and appear once in brackets where a renamed thing is first introduced on a form ("Goods received (GRN)").

### 6. Two edits that were silently ignored

- Editing a draft goods receipt: changes to the supplier or the challan date are not saved today. Save them if the service can safely take them on a draft; otherwise show those two fields as fixed text on edit.
- Editing a draft production order: a change to "For" is not saved today. Same rule.

## Tests

Per form: the essential fields are outside any fold and the folded ones inside; the fold is closed on a blank form and open when a folded field has a value or an error; posting the form with the same field names still saves exactly what it did (existing tests must pass unchanged apart from label text). Party must be chosen: blank refused with the message and typed values kept; prefill from links kept. Conditional fields: only the chosen type's fields are shown and the server result is unchanged. The two edit fixes. No migration. User guide updated.

## Out of scope

Reordering or redesigning line-entry tables; per-field inline errors on transaction forms; any change to what is validated or posted.
