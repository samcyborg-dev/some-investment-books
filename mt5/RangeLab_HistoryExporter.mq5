//+------------------------------------------------------------------+
//| RangeLab_HistoryExporter.mq5                                     |
//|                                                                  |
//| Export-only MT5 script. It reads the broker's locally available  |
//| history and writes raw bars to CSV. It never sends orders.       |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs
#property version   "1.00"
#property description "RangeLab historical OHLCV exporter; no trading functions or order requests."

input string          InpSymbol                  = "";
input ENUM_TIMEFRAMES InpTimeframe               = PERIOD_M5;
input datetime        InpStartDate               = D'2020.01.01 00:00';
input datetime        InpEndDate                 = 0;       // 0 = latest available closed bar
input int             InpBars                    = 0;       // >0 overrides dates; 0 = use date range
input bool            InpClosedBarsOnly           = true;
input string          InpFileName                = "RangeLab_history.csv";
input bool            InpUseCommonFolder          = true;    // shared MT5 Common\Files folder
input bool            InpWriteHeader              = true;
input bool            InpExportNewestFirst       = false;   // default is chronological order
input int             InpChunkBars                = 20000;
input int             InpServerUtcOffsetMinutes   = 99999;  // 99999 = leave UTC column blank
input bool            InpFlushEachChunk           = true;

#define NO_UTC_OFFSET 99999

//+------------------------------------------------------------------+
//| Return the selected symbol, defaulting to the chart symbol.       |
//+------------------------------------------------------------------+
string SelectedSymbol()
  {
   string symbol=InpSymbol;
   StringTrimLeft(symbol);
   StringTrimRight(symbol);
   if(symbol=="")
      symbol=_Symbol;
   return symbol;
  }

//+------------------------------------------------------------------+
//| MT5 CopyRates can need a short period to request missing history. |
//+------------------------------------------------------------------+
int CopyRatesWithRetry(const string symbol,
                       const ENUM_TIMEFRAMES timeframe,
                       const datetime from_time,
                       const datetime to_time,
                       MqlRates &rates[])
  {
   int copied=-1;
   for(int attempt=0; attempt<6; attempt++)
     {
      ResetLastError();
      copied=CopyRates(symbol,timeframe,from_time,to_time,rates);
      if(copied>=0)
         return copied;

      int error=GetLastError();
      PrintFormat("CopyRates retry %d/5 failed for %s (%s), error %d",
                  attempt+1,symbol,EnumToString(timeframe),error);
      Sleep(500);
     }
   return copied;
  }

//+------------------------------------------------------------------+
//| Copy a position-based request, used when InpBars is supplied.     |
//+------------------------------------------------------------------+
int CopyBarsWithRetry(const string symbol,
                      const ENUM_TIMEFRAMES timeframe,
                      const int start_position,
                      const int count,
                      MqlRates &rates[])
  {
   int copied=-1;
   for(int attempt=0; attempt<6; attempt++)
     {
      ResetLastError();
      copied=CopyRates(symbol,timeframe,start_position,count,rates);
      if(copied>=0)
         return copied;

      int error=GetLastError();
      PrintFormat("CopyRates retry %d/5 failed for %s (%s), error %d",
                  attempt+1,symbol,EnumToString(timeframe),error);
      Sleep(500);
     }
   return copied;
  }

//+------------------------------------------------------------------+
//| Write one array chunk, preserving source prices and volumes.      |
//| CopyRates returns the oldest item first in the physical array.    |
//+------------------------------------------------------------------+
ulong WriteRates(const int file_handle,
                 MqlRates &rates[],
                 const int copied,
                 const string symbol,
                 const ENUM_TIMEFRAMES timeframe,
                 const int price_digits,
                 const bool newest_first,
                 datetime &last_written)
  {
   ulong written=0;
   int first= newest_first ? copied-1 : 0;
   int last = newest_first ? -1 : copied;
   int step = newest_first ? -1 : 1;

   for(int i=first; i!=last; i+=step)
     {
      datetime bar_time=rates[i].time;

      // Date ranges can include both endpoints. This prevents boundary rows
      // from being duplicated when the export is split into chunks.
      if(last_written!=0)
        {
         if(!newest_first && bar_time<=last_written)
            continue;
         if(newest_first && bar_time>=last_written)
            continue;
        }

      string utc_assumed="";
      if(InpServerUtcOffsetMinutes!=NO_UTC_OFFSET)
        {
         datetime utc_time=(datetime)((long)bar_time-(long)InpServerUtcOffsetMinutes*60);
         utc_assumed=TimeToString(utc_time,TIME_DATE|TIME_SECONDS);
        }

      FileWrite(file_handle,
                symbol,
                EnumToString(timeframe),
                LongToString((long)bar_time),
                TimeToString(bar_time,TIME_DATE|TIME_SECONDS),
                utc_assumed,
                DoubleToString(rates[i].open,price_digits),
                DoubleToString(rates[i].high,price_digits),
                DoubleToString(rates[i].low,price_digits),
                DoubleToString(rates[i].close,price_digits),
                LongToString((long)rates[i].tick_volume),
                LongToString((long)rates[i].real_volume),
                IntegerToString(rates[i].spread));

      last_written=bar_time;
      written++;
     }
   return written;
  }

//+------------------------------------------------------------------+
//| Small helper for safe datetime arithmetic.                        |
//+------------------------------------------------------------------+
datetime Earlier(const datetime a,const datetime b)
  {
   return a<b ? a : b;
  }

datetime Later(const datetime a,const datetime b)
  {
   return a>b ? a : b;
  }

//+------------------------------------------------------------------+
//| Print the exact MT5 file location.                                |
//+------------------------------------------------------------------+
void PrintFileLocation(const string file_name)
  {
   string root;
   if(InpUseCommonFolder)
      root=TerminalInfoString(TERMINAL_COMMONDATA_PATH)+"\\Files\\";
   else
      root=TerminalInfoString(TERMINAL_DATA_PATH)+"\\MQL5\\Files\\";
   Print("CSV written to: ",root,file_name);
  }

//+------------------------------------------------------------------+
//| Main script entry point.                                          |
//+------------------------------------------------------------------+
void OnStart()
  {
   string symbol=SelectedSymbol();
   int timeframe_seconds=PeriodSeconds(InpTimeframe);

   if(symbol=="")
     {
      Print("Export stopped: no symbol was supplied and the chart has no symbol.");
      return;
     }
   if(timeframe_seconds<=0)
     {
      Print("Export stopped: the selected timeframe has no fixed period.");
      return;
     }
   if(InpChunkBars<100 || InpChunkBars>1000000)
     {
      Print("Export stopped: InpChunkBars must be between 100 and 1,000,000.");
      return;
     }
   if(InpBars<0 || InpBars>10000000)
     {
      Print("Export stopped: InpBars must be 0 or between 1 and 10,000,000.");
      return;
     }
   if(InpFileName=="")
     {
      Print("Export stopped: InpFileName is empty.");
      return;
     }
   if(!SymbolSelect(symbol,true))
     {
      Print("Export stopped: MT5 could not select symbol ",symbol,
            ". Check the broker's Market Watch symbol name.");
      return;
     }

   long digits_long=SymbolInfoInteger(symbol,SYMBOL_DIGITS);
   int price_digits=(int)digits_long;
   if(price_digits<0 || price_digits>10)
      price_digits=8;

   int flags=FILE_WRITE|FILE_CSV|FILE_ANSI;
   if(InpUseCommonFolder)
      flags|=FILE_COMMON;

   ResetLastError();
   int file_handle=FileOpen(InpFileName,flags,',');
   if(file_handle==INVALID_HANDLE)
     {
      Print("Export stopped: FileOpen failed with error ",GetLastError(),
            ". Check the filename and terminal file permissions.");
      return;
     }

   if(InpWriteHeader)
      FileWrite(file_handle,
                "symbol",
                "timeframe",
                "time_epoch_raw",
                "time_server",
                "time_utc_assumed",
                "open",
                "high",
                "low",
                "close",
                "tick_volume",
                "real_volume",
                "spread_points");

   ulong total_written=0;
   datetime last_written=0;
   MqlRates rates[];
   ArraySetAsSeries(rates,false);

   // In bars mode, position 0 is the still-forming bar. Position 1 is the
   // newest completed bar, which is the safe default for research exports.
   if(InpBars>0)
     {
      int start_position=InpClosedBarsOnly ? 1 : 0;
      int copied=CopyBarsWithRetry(symbol,InpTimeframe,start_position,InpBars,rates);
      if(copied<=0)
        {
         Print("Export stopped: MT5 returned no bars for ",symbol,".");
         FileClose(file_handle);
         return;
        }

      total_written=WriteRates(file_handle,rates,copied,symbol,InpTimeframe,
                               price_digits,InpExportNewestFirst,last_written);
     }
   else
     {
      MqlRates probe[];
      ArraySetAsSeries(probe,false);
      int probe_copied=CopyBarsWithRetry(symbol,InpTimeframe,1,1,probe);
      if(probe_copied<=0)
        {
         Print("Export stopped: MT5 has no completed bars for ",symbol,
               ". Open the symbol chart and request more history first.");
         FileClose(file_handle);
         return;
        }

      datetime latest_closed=probe[0].time;
      datetime range_end=InpEndDate==0 ? latest_closed : InpEndDate;
      if(InpClosedBarsOnly && range_end>latest_closed)
         range_end=latest_closed;
      datetime range_start=InpStartDate;

      if(range_start<=0 || range_start>range_end)
        {
         Print("Export stopped: start/end dates are invalid. Start=",
               TimeToString(range_start,TIME_DATE|TIME_SECONDS),
               " End=",TimeToString(range_end,TIME_DATE|TIME_SECONDS));
         FileClose(file_handle);
         return;
        }

      long chunk_seconds=(long)InpChunkBars*(long)timeframe_seconds;

      if(!InpExportNewestFirst)
        {
         datetime cursor=range_start;
         while(cursor<=range_end && !IsStopped())
           {
            datetime proposed_end=(datetime)((long)cursor+chunk_seconds-timeframe_seconds);
            datetime chunk_end=Earlier(proposed_end,range_end);
            int copied=CopyRatesWithRetry(symbol,InpTimeframe,cursor,chunk_end,rates);
            if(copied<0)
              {
               Print("Export stopped: MT5 could not read a history chunk.");
               break;
              }
            if(copied>0)
               total_written+=WriteRates(file_handle,rates,copied,symbol,InpTimeframe,
                                         price_digits,false,last_written);
            if(InpFlushEachChunk)
               FileFlush(file_handle);
            if(chunk_end>=range_end)
               break;
            cursor=(datetime)((long)chunk_end+timeframe_seconds);
           }
        }
      else
        {
         datetime cursor=range_end;
         while(cursor>=range_start && !IsStopped())
           {
            datetime proposed_start=(datetime)((long)cursor-chunk_seconds+timeframe_seconds);
            datetime chunk_start=Later(proposed_start,range_start);
            int copied=CopyRatesWithRetry(symbol,InpTimeframe,chunk_start,cursor,rates);
            if(copied<0)
              {
               Print("Export stopped: MT5 could not read a history chunk.");
               break;
              }
            if(copied>0)
               total_written+=WriteRates(file_handle,rates,copied,symbol,InpTimeframe,
                                         price_digits,true,last_written);
            if(InpFlushEachChunk)
               FileFlush(file_handle);
            if(chunk_start<=range_start)
               break;
            cursor=(datetime)((long)chunk_start-timeframe_seconds);
           }
        }
     }

   FileFlush(file_handle);
   FileClose(file_handle);

   if(total_written==0)
     {
      Print("No rows were exported. The CSV may contain only its header; no prices were generated.");
      PrintFileLocation(InpFileName);
      return;
     }

   Print("Export complete: ",LongToString((long)total_written)," bars for ",symbol,
         " / ",EnumToString(InpTimeframe),".");
   if(InpServerUtcOffsetMinutes==NO_UTC_OFFSET)
      Print("time_utc_assumed is blank. Keep the raw broker/server time until the broker timezone is documented.");
   else
      Print("time_utc_assumed uses the fixed server UTC offset of ",
            IntegerToString(InpServerUtcOffsetMinutes)," minutes; verify historical DST changes separately.");
   PrintFileLocation(InpFileName);
  }
//+------------------------------------------------------------------+
