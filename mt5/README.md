# RangeLab MT5 history exporter

`RangeLab_HistoryExporter.mq5` is an **export-only MT5 script**. It reads the selected broker symbol's locally available history and writes bar values to CSV. It contains no `CTrade`, `OrderSend`, position-management or live-trading code.

## Chromebook / WebTerminal limitation

A Chromebook browser running **MT5 WebTerminal cannot install or execute `.mq5` files**. WebTerminal does not provide MetaEditor, the MQL5 `Scripts` folder or a general local-file API for custom scripts. The exporter must run in desktop MT5 with MetaEditor, normally on Windows.

From a Chromebook, the practical options are:

1. Use a Windows cloud desktop or VPS, connect to it through Chrome, install desktop MT5, compile this script in MetaEditor, run it, and download the CSV back to the Chromebook.
2. Use a broker portal's own historical-data export if it provides one, then normalize the CSV before importing it into Range Lab.
3. Use a Linux container/Wine installation only if you are comfortable with an unsupported MT5 desktop setup; this is broker- and Chromebook-architecture-dependent.

Do not paste the `.mq5` source into WebTerminal; it will not run there. If your broker offers a separate web export/API, its exact symbol and timestamp convention must be recorded before using the data.

## What it exports

Each row contains:

- `symbol`
- `timeframe`
- `time_epoch_raw`
- `time_server`
- `time_utc_assumed`
- `open`, `high`, `low`, `close`
- `tick_volume`, `real_volume`
- `spread_points`

The default order is oldest to newest. The exporter preserves the broker's raw timestamp and both MT5 volume fields. It does not fill gaps, round prices, relabel contracts or replace missing real volume with invented values.

## Install and run

1. In MetaTrader 5, open **File → Open Data Folder**.
2. Open `MQL5/Scripts/` and copy `RangeLab_HistoryExporter.mq5` there. You can also place it in the shared `MQL5/Scripts/` folder if you want to run it from more than one MT5 terminal.
3. Open MetaEditor, open the file, and press **Compile**.
4. In MT5, open **View → Navigator → Scripts** and drag `RangeLab_HistoryExporter` onto any chart.
5. Set the inputs:
   - `InpSymbol`: the broker's exact Market Watch name, including a suffix if present. Blank means the chart symbol.
   - `InpTimeframe`: normally `PERIOD_M5` for the ORB research.
   - `InpStartDate` and `InpEndDate`: the historical range. The dates use the broker/terminal's displayed server clock.
   - `InpBars`: set to a positive number to export the newest N bars instead of using the date range.
   - `InpClosedBarsOnly=true`: recommended; excludes the currently forming candle.
   - `InpFileName`: output filename.
   - `InpUseCommonFolder=true`: recommended; writes to the terminal-wide common `Files` folder.
6. MT5 may need to load history first. Open the symbol/timeframe chart, scroll left or press Home, wait for the history to load, then run the script again if the returned row count is shorter than expected.

The script prints the exact output path and row count in the **Experts** or **Journal** tab. With the default common-folder setting, the CSV is under the terminal common data directory's `Files` folder. Use the path printed by the script rather than guessing between multiple MT5 installations.

## Timezone warning

MT5 history is delivered in the broker's server-time convention. The exporter therefore keeps `time_server` and `time_epoch_raw` as raw source fields. `time_utc_assumed` is blank by default.

Only set `InpServerUtcOffsetMinutes` when the broker's historical server offset is documented for the whole requested period. For example, `120` means the server clock was assumed to be UTC+02:00 and the script subtracts 120 minutes to create the derived column. A fixed offset can be wrong across a daylight-saving transition, so verify it before using the derived column. No New York conversion is performed in the MT5 script.

For project validation, retain the raw columns, broker name, exact symbol, requested range, terminal build, and the exported file's SHA-256. ES and MES must be exported separately; never rename an ES file as MES.

## Connecting the export to the dashboard

The current RangeLab dashboard accepts a normalized CSV with these required fields:

```csv
timestamp,open,high,low,close,volume
```

The MT5 export intentionally keeps broker time and `tick_volume` / `real_volume` separate, so it should not be imported blindly. First confirm the broker timezone and decide whether the research volume field should be real volume or tick volume. Convert to an explicit-offset `timestamp` only after that decision, and preserve the raw MT5 CSV privately as the source artifact.

After normalization, select the matching **ES** or **MES** tab in **Market data & replay → Import**. The dashboard will perform its own timestamp, RTH, five-minute, OHLC, duplicate, gap and 0.25-point tick checks. It will not convert ES data into MES data.

## Evidence boundary

This script only obtains broker-reported historical bars. It does not establish exchange-direct provenance, continuous-contract roll methodology, data completeness, strategy profitability, or live execution quality. Those checks must happen before any ORB or MT5 performance conclusion is made.
