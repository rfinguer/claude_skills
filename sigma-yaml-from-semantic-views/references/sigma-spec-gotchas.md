# Sigma workbook spec: importer gotchas (verified on real imports)

**Every PUT publishes** (no draft option in the API; each push is a new published version in
`/v2/workbooks/{id}/version-history`). An open editor Draft is then stale: discard it, don't publish it.

Endpoint: `PUT /v2/workbooks/{workbookId}/spec` with `Content-Type: application/yaml`. A full representation is
required, and it replaces the whole workbook. `POST` and `PATCH` on that path return 404. A 400 changes nothing. The
error lists the problems of one validation stage, so expect several rounds.

**Multi-page workbooks:** PUT replaces everything. To add one report page, GET the curprice document
(`?format=json`), merge, then PUT. `sigma_cli.py push` does this. Element ids, page ids and **controlIds must be unique
across the whole workbook**, so prefix them per page (`act_`, `act-`).

| Error / symptom | Cause | Fix |
|---|---|---|
| `document.elements[N].verticalAlign: Invalid value` | text `verticalAlign` only accepts `top`, `center` or `bottom` | Use `center`, or omit it |
| `Dependency not found: 'price/item'` | A column **name** containing `/` was referenced in a formula. Sigma reads `[a/b]` as element/column | Keep `/` only in names that no formula references. Use helper columns with safe names (e.g. `h Price per Item`) and reference those |
| `yAxis2.columnIds[i]: 'x' is not listed on yAxis.columnIds` | `yAxis2` only moves existing series to the second scale | List the series in `yAxis.columnIds` too (e.g. `{columnId: x, type: line}`), then again in `yAxis2.columnIds` |
| `sort[i].columnId: Sort column not in level ... level base` | Table-level `sort` only sorts the ungrouped base rows | Put the sort on each grouping: `groupings: [{id, groupBy, calculations, sort: [{columnId, direction}]}]` |
| 404 on `/v2/workbooks/{id}/spec` | The URL code (`workbookUrlId`) was used instead of the `workbookId` UUID | Get the UUID from `GET /v2/workbooks` (`sigma_cli.py workbooks`) |
| Accepted import, but cells show `Unknown column "[X]"` / `Circular column reference to [X]` | A child element referenced a paprice column as bare `[X]` | Write `[<Paprice element name>/X]` |
| Accepted import, but the editor still shows old errors | The user has an editor Draft made from an older version (the API publishes, the draft doesn't change) | Discard the draft and reload; never publish it |
| 403 `Permission denied` on PUT | The API client's user lacks **Can edit** on that workbook | Ask the owner for Can edit, or pick another workbook |
| `rowsBy[0]: Invalid object: string` (pivot table) | Pivot shelves take objects, not ids | `rowsBy` / `columnsBy`: `[{columnId, sort: {direction}}]`; `values` stays a plain list of column ids |
| 401 on the token | Wrong API host for the org (AWS US / GCP / Azure US / AWS EU) or a wrong client | `--base-url` must be your org's host, e.g. `https://api.us.azure.sigmacomputing.com` |

## Shapes confirmed against the official schema (`sigma_schema_probe.py`)

- **Custom SQL source:** `source: {connectionId, kind: sql, statement}`. Columns use `formula: '[Custom SQL/COL]'`.
- **Native semantic view source:** `source: {connectionId, kind: semantic-view, path: [...]}`. It exists, but custom
  SQL gives control over date roles and filters.
- **Child element** (chart/table from a table): `source: {kind: table, elementId}`. Formulas reference paprice columns as
  `[<Paprice element name>/Col]` (e.g. `[Ranking by Entity/LEVEL_2]`). A bare `[Col]` means the child's own column: the import
  is accepted, but the workbook shows `Unknown column` / `Circular column reference`.
- **Column:** `{id, formula, name, description, hidden, format: {kind: number, formatString: ',.1%'}}`.
- **Grouped table:** `groupings: [{id, groupBy: [colId], calculations: [colIds]}]`, plus `order` and `frozenColumn`.
- **Conditional formats** (table):
  - `{type: backgroundScale|fontScale|dataBars, columnIds, scheme: [c1,c2,(c3)], domain: {min,mid,max}, order, nullBehavior, steps}`
  - or `{type: single, columnIds, condition: formula, formula, style: {backgroundColor, color, bold}}`
- **Controls:**
  - date range: `controlType: date-range, mode: between` (optionally `startDate`/`endDate`). It also has relative modes
    `last`/`next`/`curprice`/`custom`, but those are based on the real "now".
  - single list with manual values: `controlType: list, selectionMode: single, source: {kind: manual, valueType: text, values: [...]}, value: <default>`.
  - multi list from data: `selectionMode: multiple, values: [], source: {kind: source, source: {kind: table, elementId}, columnId}, filters: [{source: {kind: table, elementId}, columnId}, ...]`.
    One control can target several elements. `mode: exclude` with `values: [...]` gives "is not X".
  - slider: `controlType: slider, mode: '=', valueType: number, low, high, step, value`.
  - segmented: `controlType: segmented, source: {kind: manual,...}, value`.
- **Formulas referencing controls:** `[control-id]` (e.g. `Switch([p-hierarchy], "Region", [Region], ...)`).
- **Tabbed container: DO NOT USE.** Bookmark navigators become a segmented control (same kind of view) or the views are stacked
  (diffeprice elements), see SKILL.md step 4. Note: a button
  can only switch views through the `select-tab` action, which needs a tabbed container, so switch the CONTENT of one
  element with `If([control] = ...)` instead. Schema kept for reference only:
  element `{id, kind: tabbed-container, tabs: [{name}, ...]}` (the first tab is the default). The
  children go only in the layout:
  ```xml
  <TabbedContainer elementId="tabs1" type="tabbed-container" gridColumn="1 / 25" gridRow="7 / 50">
    <Tab gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
      <Element elementId="table1" gridColumn="1 / 25" gridRow="1 / 40"/>
    </Tab>
    ...
  </TabbedContainer>
  ```
- **Combo chart:** `yAxis: {columnIds: [id, {columnId, type: line}]}`, `yAxis2: {columnIds}`, `xAxis: {columnId}`,
  `tooltip: {columns: [{id}]}`.
- **Pages:** `pages: [{id, name, visibility: hidden}]`. Several `<Page>` nodes go in one `layout` block.
- **Text:** `{kind: text, body: <markdown/HTML spans>, verticalAlign: top|center|bottom}`.

- **Pivot table** (Power BI matrix with a column field, e.g. weeks): `{kind: pivot-table, source: {kind: table, elementId},
  columns: [{id, formula, name, format}], rowsBy: [{columnId, sort?}], columnsBy: [{columnId, sort?}], values: [ids],
  conditionalFormats}`. Feed it a long-format data element (one row per entity x column value) and write values as
  aggregates (`Sum([PARENT/A]) / Sum([PARENT/B])`).

## Not available / unverified
- **Color scale based on another column** (Power BI "based on field [X]"): Sigma's `backgroundScale` / `fontScale` /
  `dataBars` only take `columnIds`, `scheme`, `domain`, `order`, `nullBehavior`, `steps` (checked in the OpenAPI), so
  the scale always uses the column's own values. Apply it to the column itself and list the difference in the report.
- Grand total row on a grouped table: no key found (`summary` is the summary bar).
- A Hierarchy column header that follows the field parameter (Power BI shows "Region", "LEVEL_1"...): the Sigma column
  name is static.
- Show/hide of individual elements by a control: no spec key exists (elements have no conditional visibility).
  Switch the content of one element with `If([control] = ...)` instead.
- **Segmented control** (bookmark navigator): `{kind: control, id, controlId, controlType: segmented, name,
  source: {kind: manual, valueType: text, values: [..], labels: [..]}, value}` (checked in the OpenAPI).
- How `{{control}}` renders in SQL for text values is documented with quotes (`'apples'`). Check it on the opened
  workbook.
