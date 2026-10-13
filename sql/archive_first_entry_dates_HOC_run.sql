/* =============================================================================
   ARCHIVE REQUIREMENTS - DATE OF FIRST DATA ENTRY PER UNIT4 TABLE (HoC)
   =============================================================================
   HOW TO RUN
     Server:   mdata837
     Database: Agresso_HoC
     Output:   no file needed - copy the two result grids into the ARDP
               spreadsheet ("Date of First Data Entry in Unit4" column).

   Tables come from the ARDP Financial Management sheet. Excluded:
     - aaghocbud (FIN-010) and the financial statements / reports rows
       (FIN-008, FIN-012), since there's no table to check for those.
     - FIN-011 (not held in Unit4).

   WHAT IT DOES
     For every table it finds whichever of these columns exist and takes
     the earliest value of each:
       business : voucher_date, trans_date, order_date, deliv_date, date_from
       period   : period, period_from (YYYYPP / YYYYMM integers)
       audit    : last_update
     Missing tables or columns are skipped, not errors. Dates before 1950
     and periods outside 195000-209999 are counted as placeholders (e.g.
     1900-01-01 or 0) and left out of the "earliest" figures.

   HOW TO READ THE RESULTS
     Result 1 (summary), one row per table:
       earliest_transaction_date - best answer for transaction tables
       earliest_period_yyyypp    - fiscal period, start-year convention
                                   (e.g. 201301 = April 2013)
       earliest_last_update      - for master tables (asuheader, acuheader,
                                   aglaccounts, agldimvalue...) this is the
                                   earliest SURVIVING edit timestamp, so the
                                   real first entry is earlier. Use the
                                   earliest transaction against them instead.
     Result 2 (detail): one row per table/column, with placeholder counts.

   Read-only. Uses NOLOCK so it doesn't block the live system. Every table
   is scanned once, so agltransact may take a few minutes.
   ============================================================================= */

USE Agresso_HoC;
SET NOCOUNT ON;

DECLARE @date_floor datetime = '19500101';

IF OBJECT_ID('tempdb..#tables')  IS NOT NULL DROP TABLE #tables;
IF OBJECT_ID('tempdb..#cols')    IS NOT NULL DROP TABLE #cols;
IF OBJECT_ID('tempdb..#results') IS NOT NULL DROP TABLE #results;

CREATE TABLE #tables (seq int IDENTITY(1,1), table_name sysname PRIMARY KEY, ardp_refs varchar(100));
INSERT INTO #tables (table_name, ardp_refs) VALUES
    ('aglaccounts',    'FIN-005'),
    ('agltransact',    'FIN-005, FIN-006, FIN-007'),
    ('agldimvalue',    'FIN-005'),
    ('aglrelvalue',    'FIN-005'),
    ('atsworkerorder', 'FIN-005'),
    ('asuheader',      'FIN-006'),
    ('asutrans',       'FIN-006'),
    ('asuhistr',       'FIN-006'),
    ('acuheader',      'FIN-006'),
    ('acutrans',       'FIN-006, FIN-007'),
    ('acuhistr',       'FIN-006'),
    ('apoheader',      'FIN-006'),
    ('apodetail',      'FIN-006'),
    ('apoheadhistr',   'FIN-006'),
    ('apodethistr',    'FIN-006'),
    ('algdelivery',    'FIN-006'),
    ('aagfunds',       'FIN-010'),
    ('apltransact',    'FIN-010'),
    ('acitransaction', 'FIN-022');

CREATE TABLE #cols (column_name sysname PRIMARY KEY, kind varchar(10));
INSERT INTO #cols (column_name, kind) VALUES
    ('voucher_date', 'business'),
    ('trans_date',   'business'),
    ('order_date',   'business'),
    ('deliv_date',   'business'),
    ('date_from',    'business'),
    ('period',       'period'),
    ('period_from',  'period'),
    ('last_update',  'audit');

CREATE TABLE #results (
    table_name       sysname,
    column_name      sysname       NULL,
    kind             varchar(10)   NULL,
    data_type        sysname       NULL,
    total_rows       bigint        NULL,
    rows_with_value  bigint        NULL,
    rows_placeholder bigint        NULL,
    earliest_date    datetime      NULL,
    earliest_period  bigint        NULL,
    note             varchar(400)  NULL
);

DECLARE @table sysname, @schema sysname, @values nvarchar(max), @sql nvarchar(max);

DECLARE tbl CURSOR LOCAL FAST_FORWARD FOR
    SELECT t.table_name, s.TABLE_SCHEMA
    FROM #tables t
    LEFT JOIN INFORMATION_SCHEMA.TABLES s ON s.TABLE_NAME = t.table_name
    ORDER BY t.seq;

OPEN tbl;
FETCH NEXT FROM tbl INTO @table, @schema;

WHILE @@FETCH_STATUS = 0
BEGIN
    IF @schema IS NULL
        INSERT #results (table_name, note) VALUES (@table, 'Table not found in this database');
    ELSE
    BEGIN
        -- One VALUES row per candidate column that exists: (name, kind, type, date value, period value)
        SET @values = NULL;
        SELECT @values = COALESCE(@values + N',', N'')
             + N'(''' + c.COLUMN_NAME + N''', '''
             + CASE WHEN k.kind = 'period' AND c.DATA_TYPE IN ('date','datetime','datetime2','smalldatetime')
                    THEN 'business' ELSE k.kind END
             + N''', ''' + c.DATA_TYPE + N''', '
             + CASE WHEN c.DATA_TYPE IN ('date','datetime','datetime2','smalldatetime')
                    THEN N'TRY_CAST(t.' + QUOTENAME(c.COLUMN_NAME) + N' AS datetime), CAST(NULL AS bigint)'
                    ELSE N'CAST(NULL AS datetime), TRY_CAST(t.' + QUOTENAME(c.COLUMN_NAME) + N' AS bigint)'
               END
             + N')'
        FROM INFORMATION_SCHEMA.COLUMNS c
        JOIN #cols k ON k.column_name = c.COLUMN_NAME
        WHERE c.TABLE_SCHEMA = @schema
          AND c.TABLE_NAME   = @table
          AND c.DATA_TYPE IN ('date','datetime','datetime2','smalldatetime',
                              'int','bigint','smallint','numeric','decimal');

        IF @values IS NULL
            INSERT #results (table_name, note) VALUES (@table, 'No date/period/last_update column found');
        ELSE
        BEGIN
            SET @sql = N'
SELECT @tbl, v.col, v.kind, v.dtype,
       COUNT(*),
       SUM(CASE WHEN v.d IS NOT NULL OR v.p IS NOT NULL THEN 1 ELSE 0 END),
       SUM(CASE WHEN v.d < @floor OR v.p < 195000 OR v.p >= 210000 THEN 1 ELSE 0 END),
       MIN(CASE WHEN v.d >= @floor THEN v.d END),
       MIN(CASE WHEN v.p >= 195000 AND v.p < 210000 THEN v.p END),
       NULL
FROM ' + QUOTENAME(@schema) + N'.' + QUOTENAME(@table) + N' t WITH (NOLOCK)
CROSS APPLY (VALUES ' + @values + N') v(col, kind, dtype, d, p)
GROUP BY v.col, v.kind, v.dtype;';

            BEGIN TRY
                INSERT #results (table_name, column_name, kind, data_type, total_rows,
                                 rows_with_value, rows_placeholder, earliest_date,
                                 earliest_period, note)
                EXEC sp_executesql @sql, N'@tbl sysname, @floor datetime',
                                   @tbl = @table, @floor = @date_floor;
                IF @@ROWCOUNT = 0
                    INSERT #results (table_name, total_rows, note) VALUES (@table, 0, 'Table is empty');
            END TRY
            BEGIN CATCH
                INSERT #results (table_name, note) VALUES (@table, 'Error: ' + LEFT(ERROR_MESSAGE(), 380));
            END CATCH
        END
    END

    FETCH NEXT FROM tbl INTO @table, @schema;
END

CLOSE tbl;
DEALLOCATE tbl;

-- Result 1: summary, one row per table (paste into the ARDP sheet)
SELECT  t.ardp_refs,
        t.table_name,
        MAX(r.total_rows)                                                         AS total_rows,
        CAST(MIN(CASE WHEN r.kind = 'business' THEN r.earliest_date END) AS date) AS earliest_transaction_date,
        MIN(CASE WHEN r.kind = 'period' THEN r.earliest_period END)               AS earliest_period_yyyypp,
        CAST(MIN(CASE WHEN r.kind = 'audit' THEN r.earliest_date END) AS date)    AS earliest_last_update,
        MAX(r.note)                                                               AS note
FROM #tables t
LEFT JOIN #results r ON r.table_name = t.table_name
GROUP BY t.seq, t.ardp_refs, t.table_name
ORDER BY t.seq;

-- Result 2: detail, one row per table/column
SELECT  r.table_name, r.column_name, r.kind, r.data_type,
        r.total_rows, r.rows_with_value, r.rows_placeholder,
        CAST(r.earliest_date AS date) AS earliest_date,
        r.earliest_period,
        r.note
FROM #results r
JOIN #tables t ON t.table_name = r.table_name
ORDER BY t.seq, r.kind, r.column_name;
