# SEMANTIC_VIEW SQL patterns for Sigma custom-SQL elements

## Additive bases per entity, recomputed in Sigma
```sql
props AS (
  SELECT * FROM SEMANTIC_VIEW(<db>.<schema>.<SNAPSHOT_SV>
    DIMENSIONS DIM_ENTITY.ENTITY_ID, DIM_ENTITY.REGION, ...
    METRICS DIM_ITEM.NUM_ITEMS, SNAPSHOT.NUM_SNAPSHOT_ITEMS, TREND_30D, TREND_GOAL, EXPOSURE_NUM
    WHERE DIM_ITEM.ACTIVE_FLAG = 1 AND DIM_ENTITY.ENTITY_ID IS NOT NULL)      -- locked report filters
)
SELECT ..., NUM_ITEMS AS ITEMS,
       TREND_30D * NUM_SNAPSHOT_ITEMS AS TREND_ITEMS,           -- numerator rebuilt exactly
       TREND_GOAL * NUM_ITEMS AS TREND_GOAL_ITEMS
```
In Sigma: `<30 Trend = Sum([TREND_ITEMS]) / Sum([SNAPSHOT_ITEMS])`.

**Prove it before shipping.** Query the SV at a higher grain (e.g. `DIMENSIONS DIM_ENTITY.REGION`). Compare it with
`SUM(ratio*den)/SUM(den)` computed over the entity rows. If the denominator you weight by isn't the metric's own
denominator, the numbers drift. That is the signal to expose the real denominator as a public metric.

## One subquery per DAX date role (USERELATIONSHIP)
```sql
cal AS (SELECT DATE::DATE D, DATEID, WEEKENDING::DATE WE, TODAYDATE::DATE TD
        FROM SEMANTIC_VIEW(<SNAPSHOT_SV> DIMENSIONS DIMCALENDAR.DATE, DIMCALENDAR.DATEID, DIMCALENDAR.WEEKENDING, DIMCALENDAR.TODAYDATE
             WHERE DIMCALENDAR.XDAYSAGO_1DAYLAG >= 0 AND DIMCALENDAR.XYEARSAGO_1DAYLAG BETWEEN 0 AND 1)),   -- page filters
win AS (SELECT D, DATEID FROM cal, rng WHERE D BETWEEN <start> AND <end>),
gross AS (SELECT g.ENTITY_ID, SUM(g.GROSS_ORDERS) GROSS_ORDERS
          FROM SEMANTIC_VIEW(<TRANSACTIONS_SV> DIMENSIONS DIM_ENTITY.ENTITY_ID, ORDER_CALENDAR.DATEID
                             METRICS ORDER_FACT.GROSS_ORDERS WHERE DIM_ITEM.ACTIVE_FLAG = 1) g
          JOIN win ON win.DATEID = g.DATEID GROUP BY 1),
cxl AS (... CANCEL_CALENDAR.DATEID METRICS CANCELS, REJECTS ...)
```
Composite measures that mix roles (`Net Order = Gross Order - Cancel - Reject`) are computed in Sigma from the bases. One
SV query with a date filter would filter both roles by the same date, which is wrong.

## Relative date slicer (Power BI RelativeDates table)
```sql
anchor AS (SELECT MAX(TD) - 1 AS Y FROM cal),                     -- "1 Day Lag", model calendar, not CURRENT_DATE
rng AS (SELECT CASE COALESCE({{p-relative-date}}, 'Last 7 Days')
          WHEN 'Yesterday' THEN Y WHEN 'Last 7 Days' THEN Y - 6 WHEN 'Last 14 Days' THEN Y - 13
          WHEN 'Last 21 Days' THEN Y - 20 WHEN 'Last 30 Days' THEN Y - 29
          WHEN 'WTD (1 Day Lag)' THEN (SELECT MAX(WE) FROM cal WHERE D = Y) - 6
          WHEN 'MTD (1 Day Lag)' THEN DATE_TRUNC('month', Y)::DATE END AS RS, Y AS RE FROM anchor),
win AS (SELECT c.D, c.DATEID FROM cal c CROSS JOIN rng r
        WHERE c.D BETWEEN GREATEST(r.RS, COALESCE(<date-start>, r.RS)) AND LEAST(r.RE, COALESCE(<date-end>, r.RE)))
```
Here `<date-start>` is `TRY_TO_DATE(LEFT(TO_VARCHAR({{#formula [p-date-range].start}}), 10))`. It works whether
Sigma renders a timestamp, a date string or NULL.

## DAX calculated tables with RANKX (e.g. "Focus Entity Flag")
Calculated tables are computed at refresh time **without report filters**. Reproduce them in their own CTE, with no
locked filters:
```sql
focus_r1 AS (SELECT f.*, RANK() OVER (ORDER BY PROJ_AMT_VAR ASC NULLS LAST) PROJ_RANK FROM focus_base f),
focus AS (SELECT ENTITY_ID,
  IFF(PROJ_RANK <= 10 OR (PROJ_RANK > 10 AND
      RANK() OVER (PARTITION BY (PROJ_RANK > 10) ORDER BY TREND_VAR_PCT ASC NULLS LAST) <= 10), 'TRUE', 'FALSE') FLAG
  FROM focus_r1)
```
`RANKX(..., ASC, Skip)` corresponds to `RANK()` (ties skip).

## What-if weights (Weighted Score style)
Weights are Sigma sliders. Recompute each component per group from additive bases, for example
`Util Var % = (Sum(UTIL_PCT*ITEMS) - Sum(UTIL_GOAL_PCT*ITEMS)) / Sum(ITEMS)`. Then:
`Zn([Util Var]) * [p-w-occ] + Zn([<30 Var]) * [p-w-trend] + Zn([Price Var]) * [p-w-price]`.

## Validation queries (Snowflake)
- Replace each placeholder with a literal and run every option (each relative date, empty controls, an explicit range).
- Compare the totals with direct SV queries using the same filters, e.g. `METRICS ORDER_FACT.GROSS_ORDERS WHERE ORDER_CALENDAR.DATEID BETWEEN ...`.
- Check that every fact joins to the entity dimension (`GROUP BY ENTITY_ID IS NULL`). Synthetic data often has
  keys that don't match, so a measure comes back empty per entity.

## More semantic-view patterns
- **A filter that causes "Multi-path"** (e.g. an item-dimension filter on a table that reaches the entity dimension
  only through the calendar): drop the filter in that subquery and JOIN it to an entity set that was queried WITH the
  filter. In DAX the item filter propagates to the entity, so the result is the same.
- **A metric that can't be grouped by entity in one SV** (Multi-path) can often be rebuilt from additive metrics of
  another SV that can, e.g. `exp_lt30 = NTV_total - (exp_gt30 + prelease_gt30) - prelease_lt30`. Prove the identity on
  the ungrouped total of both SVs before using it.
- **A metric that exists in one SV but fails "Multi-path" when grouped by entity**, while another SV has the same
  tables joined without the extra path (e.g. a sibling metric there already groups fine): with the user's OK, copy the
  definition into that SV (its private `H_*` helpers + the public metric, same expressions), validate with `TRUE`,
  deploy, and check that the ungrouped totals of both SVs are equal and that the per-entity rows sum to the total.
- **A per-entity attribute that only exists as a FACT** (DAX `Average(Dim[col])`): facts can't be returned with the
  entity key, so add a public metric `AVG(<TABLE>.<FACT>)` (with the user's OK); Sigma then uses `Avg([col])` per group.
- **Window counts** (`COUNTROWS` over the last N days): use the SV's own `COUNT_IF` window metric. Summing a
  `SUM(<count column>)` metric by a day dimension is not the same count.

## Lessons from the Goals page (PROJ-271)
- **Averages (AVERAGE / AVERAGEA) are not additive**: return SUM and COUNT per entity (add public metrics if needed)
  and let Sigma divide per group. A ratio of two averages over the same rows still needs both counts (blanks differ).
- **Date-windowed counts over a fact-only table** (e.g. Survey promoters in the last 30 days): FACTS can't be queried
  with the date DIMENSION, so add a public metric with the window inside it, e.g.
  `SUM(CASE WHEN DATEDIFF('day', SURVEY.DATESUBMITTED, <last sunday>) BETWEEN 0 AND 29 THEN SURVEY.PROMOTER END)`.
- **"Multi-path in many-to-many"** on a table that reaches DIM_ENTITY through two paths (e.g. TURNOVER via DIM_ITEM and
  DIMCALENDAR): group by that table's own entity key (`DIMENSIONS TURNOVER.ENTITY_ID`) instead of `DIM_ENTITY.ENTITY_ID`.
- **"N days ago" history** (DimCalendar[xDaysAgo_1DayLag] = N): the SV keeps the sums as private helpers
  (`H_SUM_<COL>_LAG1_D<N>`); add public copies with the same expr and return them per entity.
- **Field parameter with two saved fields** (e.g. LEVEL_1, Region): two single-select lists (`Hierarchy`, `Hierarchy (2nd
  level)` with `(None)`) and one grouping with `groupBy: [h1, h2]`; custom sort columns (RegionSort) go in the grouping
  `sort` through a hidden `If([ctl] = "Region", Min([REGION_SORT]), Null)` column.

